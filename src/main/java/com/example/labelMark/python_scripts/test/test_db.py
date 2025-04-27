import os
import psycopg2
import rasterio
import numpy as np
from rasterio.features import rasterize
from shapely.geometry import Polygon
import matplotlib.pyplot as plt

# 数据库连接信息 (请替换为你的实际信息)
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"

# 遥感影像路径和 task_id (请替换为你的实际信息)
IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"
TASK_ID = 127

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

# -------------------- 掩膜生成函数 --------------------
def create_label_mask(image_path, labels_data, num_classes, type_id_to_class_index, background_class_index):
    """根据标签数据创建标签掩膜，使用地理坐标 (EPSG:3857)"""
    with rasterio.open(image_path) as src:
        transform = src.transform
        img_height = src.height
        img_width = src.width
        # 检查 TIFF 的坐标系
        print(f"TIFF 文件的坐标系: {src.crs}")
        if src.crs != 'EPSG:3857':
            print("警告: TIFF 文件的坐标系不是 EPSG:3857，可能导致掩膜生成错误！")

    # 初始化掩膜，背景类为 background_class_index
    mask = np.full((img_height, img_width), background_class_index, dtype=np.uint8)

    # 存储所有需要光栅化的形状
    shapes = []
    for _, geom_str, type_id, *_ in labels_data:
        try:
            # 解析几何字符串为坐标列表 (假设 geom 是 EPSG:3857 坐标)
            coords_str_list = geom_str.split(',')
            coords_list = []
            for i in range(0, len(coords_str_list), 2):
                x = float(coords_str_list[i].strip())
                y = float(coords_str_list[i+1].strip())
                coords_list.append((x, y))

            # 创建多边形，直接使用地理坐标
            polygon = Polygon(coords_list)

            # 获取类别索引
            class_index = type_id_to_class_index.get(type_id)
            if class_index is not None:
                shapes.append((polygon, int(class_index)))
            else:
                print(f"警告: type_id {type_id} 未在映射中找到，已跳过。")
        except (ValueError, IndexError) as e:
            print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
            continue

    # 使用 rasterio.features.rasterize 直接将地理坐标光栅化到掩膜
    if shapes:
        try:
            mask = rasterio.features.rasterize(
                shapes=shapes,
                out_shape=(img_height, img_width),
                fill=background_class_index,  # 背景值
                transform=transform,          # 使用影像的仿射变换
                all_touched=True,            # 确保所有接触到的像素都被填充
                dtype=np.uint8
            )
        except ValueError as e:
            print(f"光栅化多边形时出错: {e}")
            return mask

    return mask

# -------------------- 可视化函数 --------------------
def visualize_mask(mask, num_classes, output_path="original_mask.png"):
    """可视化掩膜"""
    class_colors = plt.cm.get_cmap('tab20', num_classes)
    colored_mask = class_colors(mask / num_classes)[:, :, :3]
    plt.figure(figsize=(8, 8))
    plt.imshow(colored_mask)
    plt.title("Original Mask from Database")
    plt.axis('off')
    plt.savefig(output_path)
    plt.close()
    print(f"掩膜可视化已保存至 {output_path}")

# -------------------- 主函数 --------------------
def main():
    # 1. 连接数据库
    conn = connect_db()
    if conn is None:
        return

    # 2. 获取标签数据
    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        print(f"task_id {TASK_ID} 未找到标签数据，请检查数据库。")
        conn.close()
        return

    # 3. 动态确定分类数量和创建类别映射
    type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
    num_classes = len(type_ids_from_db) + 1  # +1 表示背景类
    print(f"检测到 {num_classes} 个类别 (包括背景)")

    type_id_to_class_index = {type_id: index for index, type_id in enumerate(type_ids_from_db)}
    background_class_index = num_classes - 1

    print(f"Type ID 到类别索引的映射: {type_id_to_class_index}")
    print(f"背景类别索引: {background_class_index}")

    # 4. 生成掩膜
    mask = create_label_mask(IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, background_class_index)

    # 5. 可视化掩膜
    visualize_mask(mask, num_classes)

    # 6. 关闭数据库连接
    conn.close()
    print("掩膜测试完成！")

if __name__ == "__main__":
    main()