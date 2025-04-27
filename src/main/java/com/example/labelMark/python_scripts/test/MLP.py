import os
import sys
import psycopg2
import rasterio
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from shapely.geometry import Polygon
import rasterio.features
import cv2
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 数据库连接信息（请替换为实际信息）
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"

# -------------------- 数据库操作函数 --------------------
def connect_db():
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER,
            password=DB_PASSWORD, port=DB_PORT
        )
        logging.info("成功连接到数据库")
        return conn
    except psycopg2.Error as e:
        logging.error(f"数据库连接错误: {e}")
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
        logging.error(f"获取标签数据错误: {e}")
        return []

def delete_existing_results_db(conn, task_id):
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        delete_query = f"DELETE FROM {TABLE_NAME} WHERE task_id = %s"
        cursor.execute(delete_query, (task_id,))
        conn.commit()
        logging.info(f"已删除 task_id {task_id} 的旧数据")
    except psycopg2.Error as e:
        logging.error(f"删除旧数据错误: {e}")
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
            logging.info(f"分割结果已写入数据库，task_id: {task_id}")
        except Exception as e:
            logging.error(f"写入数据库错误: {e}")
            conn.rollback()
    cursor.close()

# -------------------- 超像素分割函数 --------------------
def superpixel_segmentation_lsc(image_path, region_size=10, ratio=0.075):
    image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"无法读取图像: {image_path}")
    if len(image.shape) == 2:
        image = image[:, :, np.newaxis]
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    lsc = cv2.ximgproc.createSuperpixelLSC(image, region_size=region_size, ratio=ratio)
    lsc.iterate(num_iterations=10)
    segments = lsc.getLabels()
    num_superpixels = lsc.getNumberOfSuperpixels()
    logging.info(f"超像素分割完成，生成 {num_superpixels} 个超像素")
    return image, segments, num_superpixels

# -------------------- 数据处理函数 --------------------
def create_class_masks(labels_data, transform, img_height, img_width, type_id_to_class_index):
    masks = {type_id: np.zeros((img_height, img_width), dtype=np.uint8) for type_id in type_id_to_class_index.keys()}
    for _, geom_str, type_id, *_ in labels_data:
        try:
            coords_list = [(float(geom_str.split(',')[i].strip()), float(geom_str.split(',')[i+1].strip()))
                           for i in range(0, len(geom_str.split(',')), 2)]
            polygon = Polygon(coords_list)
            if type_id in type_id_to_class_index:
                shapes = [(polygon, 1)]
                mask = rasterio.features.rasterize(
                    shapes=shapes, out_shape=(img_height, img_width),
                    fill=0, transform=transform, all_touched=True, dtype=np.uint8
                )
                masks[type_id] = np.maximum(masks[type_id], mask)
        except Exception as e:
            logging.error(f"处理几何数据错误: {e}")
            continue
    return masks

def assign_superpixel_labels(segments, masks, num_superpixels):
    superpixel_labels = np.full(num_superpixels, -1, dtype=int)
    for sp_idx in range(num_superpixels):
        sp_mask = (segments == sp_idx)
        max_overlap = 0
        assigned_type_id = -1
        for type_id, class_mask in masks.items():
            overlap = np.sum(np.logical_and(sp_mask, class_mask))
            if overlap > max_overlap:
                max_overlap = overlap
                assigned_type_id = type_id
        if assigned_type_id != -1:
            superpixel_labels[sp_idx] = assigned_type_id
    return superpixel_labels

def extract_superpixel_features(image, segments, num_superpixels):
    features = []
    for sp_idx in range(num_superpixels):
        sp_mask = (segments == sp_idx)
        sp_pixels = image[sp_mask]
        if sp_pixels.size > 0:
            mean_val = np.mean(sp_pixels, axis=0)
            std_val = np.std(sp_pixels, axis=0)
            feature = np.concatenate([mean_val, std_val])
            features.append(feature)
        else:
            features.append(np.zeros(image.shape[-1] * 2))
    return np.array(features)

def prepare_training_data(features, superpixel_labels, type_id_to_class_index, train_ratio=0.8):
    labeled_indices = np.where(superpixel_labels != -1)[0]
    if len(labeled_indices) == 0:
        raise ValueError("没有可用的带标签超像素用于训练")
    # 将 type_id 转换为连续的类别索引
    y_mapped = np.array([type_id_to_class_index[label] for label in superpixel_labels[labeled_indices]])
    np.random.shuffle(labeled_indices)
    split_idx = int(len(labeled_indices) * train_ratio)
    train_indices = labeled_indices[:split_idx]
    val_indices = labeled_indices[split_idx:]
    X_train = features[train_indices]
    y_train = y_mapped[:split_idx]
    X_val = features[val_indices] if len(val_indices) > 0 else np.array([])
    y_val = y_mapped[split_idx:] if len(val_indices) > 0 else np.array([])
    logging.info(f"训练集大小: {len(X_train)}, 验证集大小: {len(X_val)}")
    logging.info(f"y_train 范围: [{y_train.min()}, {y_train.max()}], y_val 范围: [{y_val.min() if y_val.size > 0 else -1}, {y_val.max() if y_val.size > 0 else -1}]")
    return X_train, y_train, X_val, y_val

# -------------------- MLP 模型定义 --------------------
class MLP(nn.Module):
    def __init__(self, input_dim, num_classes):
        super(MLP, self).__init__()
        self.fc1 = nn.Linear(input_dim, 256)  # 8 -> 256
        self.fc2 = nn.Linear(256, 128)        # 256 -> 128
        self.fc3 = nn.Linear(128, 64)         # 128 -> 64
        self.fc4 = nn.Linear(64, num_classes) # 64 -> 2
    
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = torch.relu(self.fc3(x))
        x = self.fc4(x)
        return x
# -------------------- 训练和预测函数 --------------------
def train_mlp(model, X_train, y_train, X_val, y_val, criterion, optimizer, num_epochs, device):
    model.train()
    X_train_tensor = torch.from_numpy(X_train).float().to(device)
    y_train_tensor = torch.from_numpy(y_train).long().to(device)
    has_validation = X_val.size > 0
    if has_validation:
        X_val_tensor = torch.from_numpy(X_val).float().to(device)
        y_val_tensor = torch.from_numpy(y_val).long().to(device)
    
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.1)  # 每 10 个 epoch 降低学习率
    best_val_loss = float('inf')
    patience = 20
    patience_counter = 0

    for epoch in range(num_epochs):
        optimizer.zero_grad()
        outputs = model(X_train_tensor)
        loss = criterion(outputs, y_train_tensor)
        loss.backward()
        optimizer.step()
        scheduler.step()
        
        if has_validation:
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_val_tensor)
                val_loss = criterion(val_outputs, y_val_tensor)
            model.train()
            logging.info(f"Epoch [{epoch+1}/{num_epochs}], Train Loss: {loss.item():.4f}, Val Loss: {val_loss.item():.4f}")
            # 早停
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logging.info("早停触发，训练停止")
                    break
        else:
            logging.info(f"Epoch [{epoch+1}/{num_epochs}], Train Loss: {loss.item():.4f}")
    logging.info("MLP 训练完成!")

# 在 main 中调整学习率
LEARNING_RATE = 0.0001

def predict_superpixels(model, features, device):
    model.eval()
    with torch.no_grad():
        features_tensor = torch.from_numpy(features).float().to(device)
        outputs = model(features_tensor)
        _, predicted = torch.max(outputs, 1)
    return predicted.cpu().numpy()

# -------------------- 掩膜转多边形函数 --------------------
def identify_holes_and_split(mask, transform, class_index_to_type_id, min_area=30):
    polygons = {}
    for class_index in np.unique(mask):
        type_id = class_index_to_type_id.get(class_index)
        if type_id is None:
            continue
        class_mask = (mask == class_index).astype(np.uint8)
        contours, _ = cv2.findContours(class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        class_polygons = []
        for contour in contours:
            if len(contour) < 3 or cv2.contourArea(contour) < min_area:
                continue
            coords = [transform * (point[0][0], point[0][1]) for point in contour]
            coords = [(x, y) for x, y in coords]
            try:
                polygon = Polygon(coords)
                class_polygons.append(polygon)
            except Exception as e:
                logging.error(f"创建多边形错误: {e}")
        if class_polygons:
            polygons[type_id] = class_polygons
    return polygons

# -------------------- 主函数 --------------------
def main():
    TASK_ID = 137
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"
    LEARNING_RATE = 0.001
    NUM_EPOCHS = 200

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info(f"使用设备: {device}")

    conn = connect_db()
    if conn is None:
        logging.error("无法连接数据库，程序退出")
        return

    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        logging.warning(f"task_id {TASK_ID} 无标签数据")
        conn.close()
        return

    user_id = labels_data[0][3]
    status = labels_data[0][5]

    type_ids = sorted(list(set(row[2] for row in labels_data)))
    type_id_to_class_index = {tid: idx for idx, tid in enumerate(type_ids)}
    class_index_to_type_id = {idx: tid for tid, idx in type_id_to_class_index.items()}
    num_classes = len(type_ids)
    logging.info(f"类别数量: {num_classes}, 类别映射: {type_id_to_class_index}")

    image, segments, num_superpixels = superpixel_segmentation_lsc(IMAGE_PATH)

    with rasterio.open(IMAGE_PATH) as src:
        transform = src.transform
        img_height, img_width = src.height, src.width

    masks = create_class_masks(labels_data, transform, img_height, img_width, type_id_to_class_index)

    superpixel_labels = assign_superpixel_labels(segments, masks, num_superpixels)
    logging.info(f"超像素标签范围: [{superpixel_labels.min()}, {superpixel_labels.max()}]")

    features = extract_superpixel_features(image, segments, num_superpixels)
    logging.info(f"提取特征完成，特征维度: {features.shape[1]}")

    try:
        X_train, y_train, X_val, y_val = prepare_training_data(features, superpixel_labels, type_id_to_class_index)
    except ValueError as e:
        logging.error(f"准备训练数据失败: {e}")
        conn.close()
        return

    input_dim = features.shape[1]
    model = MLP(input_dim, num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    train_mlp(model, X_train, y_train, X_val, y_val, criterion, optimizer, NUM_EPOCHS, device)

    predicted_labels = predict_superpixels(model, features, device)

    predicted_mask = np.zeros_like(segments, dtype=np.uint8)
    for sp_idx in range(num_superpixels):
        sp_mask = (segments == sp_idx)
        predicted_mask[sp_mask] = predicted_labels[sp_idx]

    segmentation_polygons = identify_holes_and_split(predicted_mask, transform, class_index_to_type_id)

    delete_existing_results_db(conn, TASK_ID)
    insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

    conn.close()
    logging.info("任务完成!")

if __name__ == "__main__":
    main()