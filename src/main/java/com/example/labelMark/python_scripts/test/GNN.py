import os
import psycopg2
import rasterio
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
from torch_geometric.utils import to_networkx
from shapely.geometry import Polygon
import rasterio.features
import cv2
import networkx as nx
from superpixel import superpixel_segmentation_lsc  # 从“超像素.py”中导入

# 数据库连接信息（请替换为您的实际信息）
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
        print(f"数据库连接错误: {e}")
        return None

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
        print(f"获取标签数据错误: {e}")
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
        print(f"删除现有结果错误: {e}")
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
            print(f"写入数据库错误: {e}")
    else:
        print("没有生成任何分割多边形，未写入数据库。")
    cursor.close()

# -------------------- 图神经网络定义 --------------------
class GCN(nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super(GCN, self).__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, out_channels)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.5, training=self.training)
        x = self.conv2(x, edge_index)
        return F.log_softmax(x, dim=1)

# -------------------- 数据准备函数 --------------------
def prepare_graph_data(image_path, labels_data, type_id_to_class_index):
    """准备 PyG 的图数据"""
    # 1. 超像素分割
    segments, num_labels, _ = superpixel_segmentation_lsc(image_path, region_size=10, ratio=0.075)
    print(f"超像素分割完成，生成了 {num_labels} 个超像素。")

    # 2. 加载影像并计算特征
    with rasterio.open(image_path) as src:
        transform = src.transform
        image = src.read().astype(np.float32) / 255.0  # 归一化

    # 提取节点特征（每个超像素的平均像素值）
    x = []
    for label in range(num_labels):
        mask = (segments == label)
        feature = [np.mean(image[c][mask]) for c in range(image.shape[0])]
        x.append(feature)
    x = torch.tensor(x, dtype=torch.float)

    # 3. 构建边索引（相邻超像素）
    edge_index = []
    for i in range(segments.shape[0] - 1):
        for j in range(segments.shape[1] - 1):
            if segments[i, j] != segments[i + 1, j]:
                edge_index.append([segments[i, j], segments[i + 1, j]])
            if segments[i, j] != segments[i, j + 1]:
                edge_index.append([segments[i, j], segments[i, j + 1]])
    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()

    # 4. 根据数据库样本分配标签
    superpixel_polygons = []
    for label in range(num_labels):
        mask = (segments == label).astype(np.uint8)
        for shape, value in rasterio.features.shapes(mask, transform=transform):
            if value == 1:
                polygon = Polygon(shape['coordinates'][0])
                superpixel_polygons.append((label, polygon))
                break

    y = torch.full((num_labels,), -1, dtype=torch.long)  # 默认无标签
    sample_polygons = [(Polygon((float(x.strip()), float(y.strip())) 
                                 for x, y in zip(geom.split(',')[::2], geom.split(',')[1::2])), 
                        type_id) 
                       for _, geom, type_id, *_ in labels_data]

    for label, sp_polygon in superpixel_polygons:
        for sample_polygon, type_id in sample_polygons:
            if sp_polygon.intersects(sample_polygon):
                y[label] = type_id_to_class_index[type_id]
                break

    # 5. 创建 PyG Data 对象
    train_mask = y != -1
    test_mask = y == -1
    data = Data(x=x, edge_index=edge_index, y=y, train_mask=train_mask, test_mask=test_mask)
    data.validate(raise_on_error=True)  # 验证数据有效性
    return data, superpixel_polygons, transform

# -------------------- 主函数 --------------------
def main():
    # 遥感影像路径和 task_id（请替换为您的实际信息）
    TASK_ID = 133
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"

    # 检查 GPU 是否可用
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")

    # 连接数据库
    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return

    # 获取原始标签数据
    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
        conn.close()
        return

    # 提取 user_id 和 status
    user_id = labels_data[0][3]
    status = labels_data[0][5]

    # 动态确定类别映射
    type_ids = sorted(set(row[2] for row in labels_data))
    num_classes = len(type_ids)
    type_id_to_class_index = {tid: idx for idx, tid in enumerate(type_ids)}
    class_index_to_type_id = {idx: tid for tid, idx in type_id_to_class_index.items()}

    # 准备图数据
    data, superpixel_polygons, transform = prepare_graph_data(IMAGE_PATH, labels_data, type_id_to_class_index)

    # 初始化并训练 GCN
    model = GCN(in_channels=data.x.shape[1], hidden_channels=16, out_channels=num_classes).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)

    data = data.to(device)
    model.train()
    for epoch in range(200):
        optimizer.zero_grad()
        out = model(data)
        loss = F.nll_loss(out[data.train_mask], data.y[data.train_mask])
        loss.backward()
        optimizer.step()
        if epoch % 10 == 0:
            print(f"Epoch {epoch}, Loss: {loss.item():.4f}")

    # 预测无标签超像素
    model.eval()
    with torch.no_grad():
        pred = model(data).argmax(dim=1).cpu()

    # 分配预测结果
    segmentation_polygons = {}
    for label, (sp_label, polygon) in enumerate(superpixel_polygons):
        type_id = class_index_to_type_id[pred[label].item()]
        if type_id not in segmentation_polygons:
            segmentation_polygons[type_id] = []
        segmentation_polygons[type_id].append(polygon)

    # 写入数据库
    delete_existing_results_db(conn, TASK_ID)
    insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

    # 关闭数据库连接
    conn.close()
    print("任务完成！")

if __name__ == "__main__":
    main()