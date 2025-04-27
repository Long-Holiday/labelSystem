import os
import sys
import psycopg2
import rasterio
import numpy as np
from shapely import LineString, MultiPolygon, Point
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from shapely.geometry import Polygon
import rasterio.features
import matplotlib.pyplot as plt
import cv2
from skimage import morphology

# 数据库连接信息 (请替换为你的实际信息)
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"
TABLE_NAME2 = "task"

# -------------------- 数据库操作函数 --------------------
def connect_db():
    """连接到PostgreSQL数据库"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

def fetch_map_server_from_db(conn, task_id):
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT map_server FROM {TABLE_NAME2} WHERE task_id = %s"
        cursor.execute(query, (task_id,))
        map_server = cursor.fetchall()
        cursor.close()
        return map_server
    except psycopg2.Error as e:
        print(f"Error fetching map_server from database: {e}")
        return []

def fetch_labels_from_db(conn, task_id):
    """从数据库中获取指定 task_id 的标签数据"""
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
    """删除数据库中指定 task_id 的原有数据"""
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        delete_query = f"DELETE FROM {TABLE_NAME} WHERE task_id = %s"
        cursor.execute(delete_query, (task_id,))
        conn.commit()
        print(f"已删除 task_id {task_id} 的原有数据。")
    except psycopg2.Error as e:
        print(f"Error deleting existing results from database: {e}")
        conn.rollback()
    finally:
        cursor.close()

def insert_segmentation_results_db(conn, task_id, segmentation_polygons, user_id, status):
    """将分割结果写入数据库，使用原始坐标字符串格式"""
    if conn is None:
        return
    cursor = conn.cursor()
    insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s"

    values_list = []
    for type_id, polygons in segmentation_polygons.items():
        for polygon in polygons:
            # 提取外环坐标（已通过 connect_multiple_holes 处理）
            geom_str = ', '.join([f"{x}, {y}" for x, y in polygon.exterior.coords])
            values_list.append((cursor.mogrify("(%s, %s, %s, %s, %s)", 
                                              (geom_str, int(type_id), user_id, task_id, status)).decode('utf-8')))

    if values_list:
        values_str = ','.join(values_list)
        full_insert_query = insert_query % values_str
        try:
            cursor.execute(full_insert_query)
            conn.commit()
            print(f"分割结果已成功写入数据库 task_id {task_id}，使用 user_id: {user_id}")
        except Exception as e:
            conn.rollback()
            print(f"写入数据库时出错: {e}")
    else:
        print("没有生成任何分割多边形，未写入数据库。")

    cursor.close()
# -------------------- 数据集定义 --------------------
class RemoteSensingSegmentationDataset(Dataset):
    def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index, background_class_index):
        self.image_path = image_path
        self.labels_data = labels_data
        self.num_classes = num_classes
        self.type_id_to_class_index = type_id_to_class_index
        self.background_class_index = background_class_index
        self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)
        self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])

    def _load_image(self, image_path):
        """加载遥感影像并进行预处理"""
        try:
            with rasterio.open(image_path) as src:
                image = src.read()  # 读取所有波段 (C, H, W)
                transform = src.transform
                bounds = src.bounds
                crs = src.crs
                if crs != 'EPSG:3857':
                    print(f"警告: 图像坐标系为 {crs}，不是 EPSG:3857，可能导致掩膜生成错误！")

            image = image.astype(np.float32) / 255.0
            return image, transform, bounds, crs
        except rasterio.RasterioIOError as e:
            print(f"Error loading image: {e}")
            return None, None, None, None

    def _create_label_mask(self, labels_data, transform, img_height, img_width):
        """根据标签数据创建标签掩膜，使用地理坐标"""
        mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)

        shapes = []
        for _, geom_str, type_id, *_ in labels_data:
            try:
                coords_str_list = geom_str.split(',')
                coords_list = []
                for i in range(0, len(coords_str_list), 2):
                    x = float(coords_str_list[i].strip())
                    y = float(coords_str_list[i+1].strip())
                    coords_list.append((x, y))

                polygon = Polygon(coords_list)
                class_index = self.type_id_to_class_index.get(type_id)
                if class_index is not None:
                    shapes.append((polygon, int(class_index)))
                else:
                    print(f"警告: type_id {type_id} 未在映射中找到，已跳过。")
            except (ValueError, IndexError) as e:
                print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
                continue

        if shapes:
            try:
                mask = rasterio.features.rasterize(
                    shapes=shapes,
                    out_shape=(img_height, img_width),
                    fill=self.background_class_index,
                    transform=transform,
                    all_touched=True,
                    dtype=np.uint8
                )
            except ValueError as e:
                print(f"光栅化多边形时出错: {e}")

        return mask

    def __len__(self):
        return 1

    def __getitem__(self, idx):
        if self.image is None or self.label_mask is None:
            raise ValueError("Image or label mask is None. Check _load_image and _create_label_mask methods.")
        image_tensor = torch.from_numpy(self.image).float()
        mask_tensor = torch.from_numpy(self.label_mask).long()
        return image_tensor, mask_tensor

# -------------------- 轻量级模型定义 (简化 U-Net) --------------------
class LightUNet(nn.Module):
    def __init__(self, in_channels, num_classes):
        super(LightUNet, self).__init__()
        self.encoder_conv1 = nn.Conv2d(in_channels, 32, kernel_size=3, padding=1)
        self.encoder_conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.decoder_upconv1 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
        self.decoder_conv1 = nn.Conv2d(32 + 32, 32, kernel_size=3, padding=1)
        self.decoder_conv2 = nn.Conv2d(32, num_classes, kernel_size=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        enc1 = self.relu(self.encoder_conv1(x))
        enc2 = self.relu(self.encoder_conv2(self.pool(enc1)))
        dec1 = self.decoder_upconv1(enc2)
        dec1_upsampled = torch.nn.functional.interpolate(dec1, size=enc1.shape[-2:], mode='bilinear', align_corners=False)
        dec1_concat = torch.cat([dec1_upsampled, enc1], dim=1)
        dec2 = self.relu(self.decoder_conv1(dec1_concat))
        output = self.decoder_conv2(dec2)
        return output

# -------------------- 训练函数 --------------------
def train_model(model, dataloader, criterion, optimizer, num_epochs, device):
    model.train()
    for epoch in range(num_epochs):
        running_loss = 0.0
        for images, masks in dataloader:
            images = images.to(device)
            masks = masks.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, masks)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
        epoch_loss = running_loss / len(dataloader)
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {epoch_loss:.4f}")
    print("训练完成!")

# -------------------- 分割预测函数 --------------------
def segment_image(model, image_tensor, device, num_classes):
    model.eval()
    with torch.no_grad():
        image_tensor = image_tensor.unsqueeze(0).to(device)
        outputs = model(image_tensor)
        probabilities = torch.softmax(outputs, dim=1)
        predicted_mask = torch.argmax(probabilities, dim=1).squeeze().cpu().numpy()
    return predicted_mask

# -------------------- 掩膜转多边形函数 --------------------
import rtree.index

def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
    current_exterior = exterior_coords[:]
    
    # 初始化 Rtree
    exterior_index = rtree.index.Index()
    for idx, (x, y) in enumerate(current_exterior):
        exterior_index.insert(idx, (x, y, x, y))
    
    for idx, interior_coords in enumerate(interior_coords_list):
        min_dist = float('inf')
        best_exterior_idx = 0
        best_interior_idx = 0
        
        for i, (ix, iy) in enumerate(interior_coords):
            nearest_idx = list(exterior_index.nearest((ix, iy, ix, iy), 1))[0]
            ex, ey = current_exterior[nearest_idx]
            dist = ((ix - ex) ** 2 + (iy - ey) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                best_exterior_idx = nearest_idx
                best_interior_idx = i
        
        # 构造新外环
        new_exterior = []
        new_exterior.extend(current_exterior[:best_exterior_idx + 1])
        reordered_interior = interior_coords[best_interior_idx:] + interior_coords[:best_interior_idx]
        new_exterior.extend(reordered_interior)
        new_exterior.append(reordered_interior[0])
        new_exterior.extend(current_exterior[best_exterior_idx:])
        
        # 更新 Rtree
        current_exterior = new_exterior
        exterior_index = rtree.index.Index()  # 重建（可选：动态插入）
        for j, (x, y) in enumerate(current_exterior):
            exterior_index.insert(j, (x, y, x, y))
    
    return current_exterior

# def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
#     """将多个内环依次连接到外环，形成单一无孔洞多边形
#     具体算法:
#     1. 对于每个内环，找到与外环最近的点对
#     2. 在外环对应点后插入内环的全部坐标点，首尾相接
#     3. 重复内环的第一个点，确保闭合
#     4. 继续外环的剩余部分
#     """
#     current_exterior = exterior_coords[:]
    
#     for idx, interior_coords in enumerate(interior_coords_list):
#         exterior_points = [Point(x, y) for x, y in current_exterior]
#         interior_points = [Point(x, y) for x, y in interior_coords]
        
#         min_dist = float('inf')
#         best_exterior_idx = 0
#         best_interior_idx = 0
        
#         for i, interior_point in enumerate(interior_points):
#             for j, exterior_point in enumerate(exterior_points):
#                 dist = interior_point.distance(exterior_point)
#                 if dist < min_dist:
#                     min_dist = dist
#                     best_exterior_idx = j
#                     best_interior_idx = i
        
#         # if min_dist > max_distance:
#         #     print(f"内环 {idx}: 距离 {min_dist:.4f} 超过阈值 {max_distance}，跳过连接")
#         #     continue
        
#         # 在外环对应点后插入内环的全部坐标点
#         new_exterior = []
#         new_exterior.extend(current_exterior[:best_exterior_idx + 1])
#         reordered_interior = (
#             interior_coords[best_interior_idx:] + #从最近点到内环末尾
#             interior_coords[:best_interior_idx]   #从内环开头到最近点
#         )
#         # 重新排序内环坐标
#         new_exterior.extend(reordered_interior)
#         #添加内环起点以确保闭合（现在是重排后的最后一个点）
#         new_exterior.append(reordered_interior[0])
#         # 添加外环剩余部分
#         new_exterior.extend(current_exterior[best_exterior_idx:])
        
#         current_exterior = new_exterior
    
#     return current_exterior

def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index, min_area=30):
    """将掩膜转换为多边形，使用 connect_multiple_holes 处理孔洞，不处理自相交"""
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
                # 转换外环坐标为地理坐标
                exterior_coords = [transform * (point[0][0], point[0][1]) for point in contours[i]]
                exterior_coords = [(x, y) for x, y in exterior_coords]
                
                # 收集内环（孔洞）
                interior_contours = []
                hole_idx = hierarchy[0][i][2]
                while hole_idx != -1:
                    if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
                        interior_coords = [transform * (point[0][0], point[0][1]) for point in contours[hole_idx]]
                        interior_coords = [(x, y) for x, y in interior_coords]
                        interior_contours.append(interior_coords)
                    hole_idx = hierarchy[0][hole_idx][0]
                
                # 使用 connect_multiple_holes 处理孔洞
                if interior_contours:
                    final_coords = connect_multiple_holes(exterior_coords, interior_contours, max_distance=1000.0)
                else:
                    final_coords = exterior_coords
                
                # 创建多边形，不检查或处理自相交
                try:
                    polygon = Polygon(final_coords)
                    class_polygons.append(polygon)
                except Exception as e:
                    print(f"创建多边形时出错: {e}")
            i += 1
        
        if class_polygons:
            polygons[type_id] = class_polygons
    
    return polygons

# def post_process_mask(mask, kernel_size=3):
#     """后处理掩膜：轻度处理以保留孔洞"""
#     mask = mask.astype(np.uint8)
#     kernel = np.ones((kernel_size, kernel_size), np.uint8)
#     mask_processed = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)  # 仅去除噪声
#     plt.imshow(mask, cmap='gray')
#     plt.title("Raw Predicted Mask")
#     plt.savefig("raw_predicted_mask.png")
#     plt.close()
#     plt.imshow(mask_processed, cmap='gray')
#     plt.title("Post-Processed Mask")
#     plt.savefig("post_processed_mask.png")
#     plt.close()
#     print("原始掩膜已保存到 raw_predicted_mask.png，后处理掩膜已保存到 post_processed_mask.png")
#     return mask_processed

def post_process_mask(mask, min_object_size=10, hole_size_threshold=20, boundary_smoothing=3):
    """
    Enhanced mask post-processing to improve segmentation quality
    
    Parameters:
    -----------
    mask : numpy.ndarray
        The raw segmentation mask
    min_object_size : int
        Minimum size (in pixels) for objects to keep
    hole_size_threshold : int
        Maximum size of holes to fill
    boundary_smoothing : int
        Kernel size for boundary smoothing operations
    
    Returns:
    --------
    numpy.ndarray
        Processed segmentation mask
    """
    import cv2
    import numpy as np
    import matplotlib.pyplot as plt
    from skimage import morphology
    from skimage.measure import regionprops, label  # Import from correct module
    
    # Step 1: Keep original mask for comparison
    original_mask = mask.copy().astype(np.uint8)
    
    # Track unique classes to process each separately
    unique_classes = np.unique(mask)
    processed_mask = np.zeros_like(mask, dtype=np.uint8)
    
    for class_idx in unique_classes:
        if class_idx == 0:  # Skip background class if it's 0
            continue
            
        # Extract binary mask for current class
        class_mask = (mask == class_idx).astype(np.uint8)
        
        # Step 2: Remove small objects
        labeled_mask = label(class_mask)  # Using skimage.measure.label
        properties = regionprops(labeled_mask)  # Using skimage.measure.regionprops
        for prop in properties:
            if prop.area < min_object_size:
                labeled_mask[labeled_mask == prop.label] = 0
        cleaned_mask = (labeled_mask > 0).astype(np.uint8)
        
        # Step 3: Fill small holes within objects
        filled_mask = cleaned_mask.copy()
        contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            # Create a mask of just this contour and fill it
            temp_mask = np.zeros_like(cleaned_mask)
            cv2.drawContours(temp_mask, [contour], 0, 1, -1)
            
            # Find holes in this contour
            temp_mask_inv = 1 - temp_mask
            # Label connected components in the inverse (to find holes)
            holes = label(temp_mask_inv)  # Using skimage.measure.label
            hole_props = regionprops(holes)  # Using skimage.measure.regionprops
            
            # Fill small holes
            for hole in hole_props:
                # Skip the "outside" - which is typically the largest region
                if hole.area < hole_size_threshold and hole.area > 0:
                    filled_mask[holes == hole.label] = 1
        
        # Step 4: Smooth boundaries while preserving shape
        kernel = np.ones((boundary_smoothing, boundary_smoothing), np.uint8)
        # Apply slight closing to connect nearby features
        smoothed_mask = cv2.morphologyEx(filled_mask, cv2.MORPH_CLOSE, kernel)
        # Then slight opening to remove small protrusions
        smoothed_mask = cv2.morphologyEx(smoothed_mask, cv2.MORPH_OPEN, kernel)
        
        # Step 5: Apply Gaussian blur and re-threshold to smooth boundaries
        blurred = cv2.GaussianBlur(smoothed_mask.astype(np.float32), (5, 5), 0)
        smoothed_mask = (blurred > 0.5).astype(np.uint8)
        
        # Assign processed mask back to the appropriate class
        processed_mask[smoothed_mask == 1] = class_idx
    
    # Create visualization of results
    plt.figure(figsize=(15, 5))
    
    plt.subplot(131)
    plt.imshow(original_mask, cmap='tab20')
    plt.title("Raw Predicted Mask")
    plt.axis('off')
    
    plt.subplot(132)
    plt.imshow(processed_mask, cmap='tab20')
    plt.title("Post-Processed Mask")
    plt.axis('off')
    
    # Show the difference
    difference = np.zeros_like(original_mask)
    difference[(original_mask != processed_mask) & (original_mask > 0)] = 1  # Removed areas
    difference[(original_mask != processed_mask) & (processed_mask > 0) & (original_mask == 0)] = 2  # Added areas
    
    plt.subplot(133)
    plt.imshow(difference, cmap='coolwarm')
    plt.title("Changes (Red: Removed, Blue: Added)")
    plt.axis('off')
    
    plt.tight_layout()
    plt.savefig("mask_processing_comparison.png")
    plt.close()
    
    # Save individual masks
    plt.figure(figsize=(8, 8))
    plt.imshow(original_mask, cmap='tab20')
    plt.title("Raw Predicted Mask")
    plt.axis('off')
    plt.savefig("raw_predicted_mask.png")
    plt.close()
    
    plt.figure(figsize=(8, 8))
    plt.imshow(processed_mask, cmap='tab20')
    plt.title("Post-Processed Mask")
    plt.axis('off')
    plt.savefig("post_processed_mask.png")
    plt.close()
    
    print("掩膜处理结果比较已保存到 mask_processing_comparison.png")
    print("原始掩膜已保存到 raw_predicted_mask.png，后处理掩膜已保存到 post_processed_mask.png")
    
    return processed_mask
# -------------------- 可视化函数 --------------------
def visualize_results(image_np, label_mask_np, predicted_mask_np, num_classes, output_path_prefix="segmentation_result"):
    """可视化原始图像、真实掩膜和预测掩膜"""
    class_colors = plt.cm.get_cmap('tab20', num_classes)
    colored_label_mask = class_colors(label_mask_np / num_classes)[:, :, :3]
    colored_predicted_mask = class_colors(predicted_mask_np / num_classes)[:, :, :3]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(np.transpose(image_np[:3, :, :], (1, 2, 0)))
    axes[0].set_title("Original Image (RGB)")
    axes[0].axis('off')
    axes[1].imshow(colored_label_mask)
    axes[1].set_title("Ground Truth Mask")
    axes[1].axis('off')
    axes[2].imshow(colored_predicted_mask)
    axes[2].set_title("Predicted Mask")
    axes[2].axis('off')
    plt.tight_layout()
    plt.savefig(f"{output_path_prefix}_masks.png")
    plt.close()

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(np.transpose(image_np[:3, :, :], (1, 2, 0)))
    ax.imshow(colored_predicted_mask, alpha=0.5)
    ax.set_title("Segmentation Overlay")
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(f"{output_path_prefix}_overlay.png")
    plt.close()
    print(f"可视化结果已保存到 {output_path_prefix}_*.png")

def visualize_original_mask(dataset, output_path="original_mask.png"):
    """可视化从数据库生成的原始掩膜"""
    mask = dataset.label_mask
    if mask is None:
        print("Failed to create original mask for visualization.")
        return
    num_classes = dataset.num_classes
    class_colors = plt.cm.get_cmap('tab20', num_classes)
    colored_mask = class_colors(mask / num_classes)[:, :, :3]
    plt.figure(figsize=(8, 8))
    plt.imshow(colored_mask)
    plt.title("Original Mask from Database")
    plt.axis('off')
    plt.savefig(output_path)
    plt.close()
    print(f"Original mask visualization saved to {output_path}")

# -------------------- 主函数 --------------------
def main():
    # 遥感影像路径和 task_id (请替换为你的实际信息)
    # TASK_ID = int(sys.argv[1])
    # MAPFILE_PATH = sys.argv[2]
    TASK_ID = 127

    # 训练参数 (可以根据需要调整)
    BATCH_SIZE = 4
    LEARNING_RATE = 0.001
    NUM_EPOCHS = 100

    # 检查GPU是否可用
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 连接数据库
    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return

    # 获取地图服务器路径
    # map_servers = fetch_map_server_from_db(conn, TASK_ID)
    # if not map_servers:
    #     print(f"task_id {TASK_ID} 未找到地图服务器路径，请检查数据库。")
    #     conn.close()
    #     return
    # 假设 map_server 是单条记录，取第一个值
    # map_name = map_servers[0][0]  # fetchall 返回元组列表，提取第一个元组的第一个元素
    # IMAGE_PATH = f"{MAPFILE_PATH}/{map_name}.tif"  # 修正路径拼接，使用斜杠分隔
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"

    # 先获取原始标签数据以提取 user_id 和 status
    original_row_data = fetch_labels_from_db(conn, TASK_ID)
    if not original_row_data:
        print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
        conn.close()
        return

    # 检查并提取唯一的 user_id 和 status
    user_ids = set(row[3] for row in original_row_data)
    if len(user_ids) > 1:
        print(f"警告: task_id {TASK_ID} 包含多个 user_id: {user_ids}，使用第一个")
    user_id = original_row_data[0][3]  # 提取唯一的 user_id
    status = original_row_data[0][5]   # 提取原始 status

    # 用于训练的标签数据
    labels_data = original_row_data  # 直接使用原始数据进行训练

    # 动态确定分类数量和创建类别映射
    type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
    num_classes = len(type_ids_from_db) + 1
    type_id_to_class_index = {type_id: index for index, type_id in enumerate(type_ids_from_db)}
    background_class_index = num_classes - 1
    class_index_to_type_id = {index: type_id for type_id, index in type_id_to_class_index.items()}

    # 创建数据集和数据加载器
    dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, background_class_index)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE)

    # 可视化原始掩膜
    visualize_original_mask(dataset)

    # 初始化模型、损失函数和优化器
    model = LightUNet(in_channels=4, num_classes=num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # 训练模型
    train_model(model, dataloader, criterion, optimizer, NUM_EPOCHS, device)

    # 加载原始图像用于分割
    original_image_np, original_transform, _, _ = dataset._load_image(IMAGE_PATH)
    if original_image_np is None:
        print("Failed to load original image for segmentation. Exiting.")
        conn.close()
        return

# 分割预测
    original_image_tensor = torch.from_numpy(original_image_np).float()
    predicted_mask_np = segment_image(model, original_image_tensor, device, num_classes)

# 后处理掩膜
    predicted_mask_np = post_process_mask(predicted_mask_np, min_object_size=10, hole_size_threshold=100, boundary_smoothing=2)

    # 转换为多边形并处理多个内环
    segmentation_polygons = identify_holes_and_split(
        predicted_mask_np, original_transform, class_index_to_type_id, background_class_index, min_area=1
    )

    # 可视化后处理后的掩膜以调试
    plt.imshow(predicted_mask_np, cmap='tab20')
    plt.title("Post-Processed Predicted Mask")
    plt.axis('off')
    plt.savefig("post_processed_predicted_mask.png")
    plt.close()
    print("后处理后的预测掩膜已保存到 post_processed_predicted_mask.png")

    # 删除数据库中旧的分割结果
    delete_existing_results_db(conn, TASK_ID)

    # 将新分割结果写入数据库，使用原始的 user_id 和 status
    insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

    # 关闭数据库连接
    conn.close()
    print("任务完成!")

if __name__ == "__main__":
    main()