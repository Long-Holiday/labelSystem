import os
import sys
import psycopg2
import rasterio
import numpy as np
from shapely import LineString, MultiPolygon, Point, Polygon
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import rasterio.features
import cv2
from skimage import morphology
from torchvision.models.segmentation import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights
import albumentations as A
from albumentations.pytorch import ToTensorV2
from monai.losses import DiceLoss
import pydensecrf.densecrf as dcrf
from pydensecrf.utils import unary_from_labels, create_pairwise_bilateral
from skimage.segmentation import slic

# Database connection info
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"
TABLE_NAME2 = "task"

# Database functions (unchanged)
def connect_db():
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

def fetch_labels_from_db(conn, task_id):
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {TABLE_NAME} WHERE task_id = %s"
        cursor.execute(query, (task_id,))
        labels_data = cursor.fetchall()
        cursor.close()
        return labels_data
    except psycopg2.Error as e:
        print(f"Error fetching labels from database: {e}")
        return []

def delete_existing_results_db(conn, task_id):
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        delete_query = f"DELETE FROM {TABLE_NAME} WHERE task_id = %s"
        cursor.execute(delete_query, (task_id,))
        conn.commit()
        print(f"Deleted existing data for task_id {task_id}.")
    except psycopg2.Error as e:
        print(f"Error deleting existing results: {e}")
        conn.rollback()
    finally:
        cursor.close()

def insert_segmentation_results_db(conn, task_id, segmentation_polygons, user_id, status):
    if conn is None:
        return
    cursor = conn.cursor()
    insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s"
    values_list = []
    for type_id, polygons in segmentation_polygons.items():
        for polygon in polygons:
            geom_str = ', '.join([f"{x}, {y}" for x, y in polygon.exterior.coords])
            values_list.append((cursor.mogrify("(%s, %s, %s, %s, %s)", 
                                              (geom_str, int(type_id), user_id, task_id, status)).decode('utf-8')))
    if values_list:
        values_str = ','.join(values_list)
        full_insert_query = insert_query % values_str
        try:
            cursor.execute(full_insert_query)
            conn.commit()
            print(f"Segmentation results written to database for task_id {task_id}, user_id: {user_id}")
        except Exception as e:
            conn.rollback()
            print(f"Error writing to database: {e}")
    else:
        print("No segmentation polygons generated.")
    cursor.close()

class RemoteSensingSegmentationDataset(Dataset):
    def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index, background_class_index, num_patches=4):
        self.image_path = image_path
        self.labels_data = labels_data
        self.num_classes = num_classes
        self.type_id_to_class_index = type_id_to_class_index
        self.background_class_index = background_class_index
        self.num_patches = num_patches
        
        self.image, self.geo_transform, self.bounds, self.crs = self._load_image(image_path)
        h, w = self.image.shape[1], self.image.shape[2]
        crop_size = min(h, w, 256)
        
        self.transform = A.Compose([
            A.RandomRotate90(),
            A.HorizontalFlip(p=0.5),
            A.RandomCrop(height=crop_size, width=crop_size),
            A.ColorJitter(brightness=0.2, contrast=0.2, p=0.5),
            A.GaussNoise(p=0.5),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ToTensorV2(),
        ])
        
        self.label_mask = self._create_label_mask(labels_data, self.geo_transform, self.image.shape[1], self.image.shape[2])

    def _load_image(self, image_path):
        try:
            with rasterio.open(image_path) as src:
                image = src.read([1, 2, 3])  # Load RGB only
                transform = src.transform
                bounds = src.bounds
                crs = src.crs
                if crs != 'EPSG:3857':
                    print(f"Warning: Image CRS is {crs}, not EPSG:3857.")
            image = image.astype(np.float32) / 255.0
            print(f"Loaded RGB image with shape: {image.shape}")
            return image, transform, bounds, crs
        except rasterio.RasterioIOError as e:
            print(f"Error loading image: {e}")
            return None, None, None, None

    def _create_label_mask(self, labels_data, transform, img_height, img_width):
        mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)
        shapes = []
        for _, geom_str, type_id, *_ in labels_data:
            try:
                coords = [float(x.strip()) for x in geom_str.split(',')]
                coords_list = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
                polygon = Polygon(coords_list)
                class_index = self.type_id_to_class_index.get(type_id)
                if class_index is not None:
                    shapes.append((polygon, int(class_index)))
            except (ValueError, IndexError) as e:
                print(f"Error processing geometry: {e}, geom_str: {geom_str}")
                continue
        if shapes:
            try:
                mask = rasterio.features.rasterize(
                    shapes=shapes, out_shape=(img_height, img_width), fill=self.background_class_index,
                    transform=transform, all_touched=True, dtype=np.uint8
                )
            except ValueError as e:
                print(f"Error rasterizing polygons: {e}")
        return mask

    def __len__(self):
        return self.num_patches

    def __getitem__(self, idx):
        if self.image is None or self.label_mask is None:
            raise ValueError("Image or label mask is None.")
        image = self.image.transpose(1, 2, 0)  # (C, H, W) -> (H, W, C)
        mask = self.label_mask
        print(f"Original image shape: {image.shape}, mask shape: {mask.shape}")
        augmented = self.transform(image=image, mask=mask)
        print(f"Augmented image shape: {augmented['image'].shape}, mask shape: {augmented['mask'].shape}")
        return augmented['image'], augmented['mask'].long()

def train_model(model, dataloader, criterion, optimizer, num_epochs, device):
    model.train()
    for epoch in range(num_epochs):
        running_loss = 0.0
        for images, masks in dataloader:
            images, masks = images.to(device), masks.to(device)
            print(f"Input tensor shape to model: {images.shape}")
            print(f"masks shape before loss: {masks.shape}")
            
            # Ensure masks has shape (B, H, W)
            if len(masks.shape) == 4 and masks.shape[1] == 1:
                masks = masks.squeeze(1)  # Remove singleton channel dimension if present
            elif len(masks.shape) != 3:
                raise ValueError(f"Unexpected masks shape: {masks.shape}. Expected (B, H, W)")
            
            optimizer.zero_grad()
            outputs = model(images)['out']
            print(f"outputs shape: {outputs.shape}")
            loss = criterion(outputs, masks)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        epoch_loss = running_loss / len(dataloader)
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {epoch_loss:.4f}")
    print("Training completed!")

def segment_image(model, image_tensor, device, num_classes):
    model.eval()
    with torch.no_grad():
        image_tensor = image_tensor.unsqueeze(0).to(device)
        outputs = model(image_tensor)['out']
        predicted_mask = torch.argmax(outputs, dim=1).squeeze().cpu().numpy()
    return predicted_mask

def combined_loss(y_pred, y_true):
    # CrossEntropyLoss expects y_true as (B, H, W) with class indices
    ce_loss = nn.CrossEntropyLoss()(y_pred, y_true)
    
    # DiceLoss with to_onehot_y=True expects y_true to have a channel dimension
    dice_loss_fn = DiceLoss(to_onehot_y=True, softmax=True)
    y_true_dice = y_true.unsqueeze(1)  # Convert (B, H, W) to (B, 1, H, W)
    dice = dice_loss_fn(y_pred, y_true_dice)
    
    return ce_loss + dice

def post_process_crf(image, mask):
    n_labels = len(np.unique(mask))
    d = dcrf.DenseCRF2D(image.shape[1], image.shape[0], n_labels)
    U = unary_from_labels(mask, n_labels, gt_prob=0.7, zero_unsure=False)
    d.setUnaryEnergy(U)
    pairwise_energy = create_pairwise_bilateral(sdims=(10, 10), schan=(0.01,), img=image, chdim=2)
    d.addPairwiseEnergy(pairwise_energy, compat=3)
    Q = d.inference(5)
    return np.argmax(Q, axis=0).reshape(mask.shape)

def morphological_closing(mask):
    kernel = np.ones((5, 5), np.uint8)
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)

def superpixel_smoothing(mask, image):
    segments = slic(image, n_segments=100, compactness=10)
    for seg_val in np.unique(segments):
        mask[segments == seg_val] = np.bincount(mask[segments == seg_val]).argmax()
    return mask

def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
    current_exterior = exterior_coords[:]
    for interior_coords in interior_coords_list:
        exterior_points = [Point(x, y) for x, y in current_exterior]
        interior_points = [Point(x, y) for x, y in interior_coords]
        min_dist = float('inf')
        best_exterior_idx = best_interior_idx = 0
        for i, ip in enumerate(interior_points):
            for j, ep in enumerate(exterior_points):
                dist = ip.distance(ep)
                if dist < min_dist:
                    min_dist = dist
                    best_exterior_idx = j
                    best_interior_idx = i
        new_exterior = []
        new_exterior.extend(current_exterior[:best_exterior_idx + 1])
        reordered_interior = interior_coords[best_interior_idx:] + interior_coords[:best_interior_idx]
        new_exterior.extend(reordered_interior)
        new_exterior.append(reordered_interior[0])
        new_exterior.extend(current_exterior[best_exterior_idx:])
        current_exterior = new_exterior
    return current_exterior

def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index, min_area=30):
    polygons = {}
    for class_index in np.unique(mask):
        if class_index == background_class_index:
            continue
        type_id = class_index_to_type_id.get(class_index)
        if type_id is None:
            continue
        class_mask = (mask == class_index).astype(np.uint8)
        contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None or len(contours) == 0:
            continue
        class_polygons = []
        i = 0
        while i < len(contours):
            if len(contours[i]) < 3 or cv2.contourArea(contours[i]) < min_area:
                i += 1
                continue
            if hierarchy[0][i][3] == -1:
                exterior_coords = [transform * (point[0][0], point[0][1]) for point in contours[i]]
                exterior_coords = [(x, y) for x, y in exterior_coords]
                interior_contours = []
                hole_idx = hierarchy[0][i][2]
                while hole_idx != -1:
                    if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
                        interior_coords = [transform * (point[0][0], point[0][1]) for point in contours[hole_idx]]
                        interior_coords = [(x, y) for x, y in interior_coords]
                        interior_contours.append(interior_coords)
                    hole_idx = hierarchy[0][hole_idx][0]
                final_coords = connect_multiple_holes(exterior_coords, interior_contours, max_distance=1000.0) if interior_contours else exterior_coords
                try:
                    polygon = Polygon(final_coords)
                    class_polygons.append(polygon)
                except Exception as e:
                    print(f"Error creating polygon: {e}")
            i += 1
        if class_polygons:
            polygons[type_id] = class_polygons
    return polygons

def main():
    TASK_ID = 127
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"
    BATCH_SIZE = 5
    LEARNING_RATE = 0.001
    NUM_EPOCHS = 100

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    conn = connect_db()
    if conn is None:
        print("Failed to connect to database. Exiting.")
        return

    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        print(f"No label data found for task_id {TASK_ID}.")
        conn.close()
        return

    user_id = labels_data[0][3]
    status = labels_data[0][5]

    type_ids = sorted(set(row[2] for row in labels_data))
    num_classes = len(type_ids) + 1  # Unique type_ids + background
    print(f"Number of classes: {num_classes}")
    type_id_to_class_index = {tid: idx for idx, tid in enumerate(type_ids)}
    background_class_index = num_classes - 1
    class_index_to_type_id = {idx: tid for tid, idx in type_id_to_class_index.items()}

    dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, background_class_index, num_patches=4)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    # Initialize model with correct number of classes
    model = deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT)
    # Replace the final classifier layer correctly
    from torchvision.models.segmentation.deeplabv3 import DeepLabHead
    model.classifier = DeepLabHead(2048, num_classes)  # 2048 is the input channels from backbone
    model = model.to(device)

    criterion = combined_loss
    for param in model.backbone.parameters():
        param.requires_grad = False
    optimizer = optim.Adam(model.classifier.parameters(), lr=LEARNING_RATE)
    train_model(model, dataloader, criterion, optimizer, NUM_EPOCHS // 2, device)

    for param in model.backbone.parameters():
        param.requires_grad = True
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE / 10)
    train_model(model, dataloader, criterion, optimizer, NUM_EPOCHS // 2, device)

    original_image_np, original_transform, _, _ = dataset._load_image(IMAGE_PATH)
    if original_image_np is None:
        print("Failed to load image for segmentation.")
        conn.close()
        return

    original_image_tensor = torch.from_numpy(original_image_np.transpose(1, 2, 0))
    original_image_tensor = A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(image=original_image_tensor.numpy())['image']
    original_image_tensor = torch.from_numpy(original_image_tensor.transpose(2, 0, 1)).float()

    predicted_mask_np = segment_image(model, original_image_tensor, device, num_classes)
    predicted_mask_np = post_process_crf(original_image_np.transpose(1, 2, 0), predicted_mask_np)
    predicted_mask_np = morphological_closing(predicted_mask_np)
    predicted_mask_np = superpixel_smoothing(predicted_mask_np, original_image_np.transpose(1, 2, 0))

    segmentation_polygons = identify_holes_and_split(predicted_mask_np, original_transform, class_index_to_type_id, background_class_index, min_area=1)

    delete_existing_results_db(conn, TASK_ID)
    insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

    conn.close()
    print("Task completed!")

if __name__ == "__main__":
    main()