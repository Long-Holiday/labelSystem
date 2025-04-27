# import os
# import psycopg2
# import rasterio
# import numpy as np
# from shapely.geometry import Polygon
# from ultralytics import YOLO
# import shutil
# import torch
# from PIL import Image
# import cv2
# from rasterio.crs import CRS

# # 数据库连接信息 (请替换为你的实际信息)
# DB_HOST = "localhost"
# DB_NAME = "label"
# DB_USER = "postgres"
# DB_PASSWORD = "123456"
# DB_PORT = "5432"
# TABLE_NAME = "mark"
# TABLE_NAME2 = "task"

# # -------------------- 数据库操作函数 --------------------
# def connect_db():
#     """连接到 PostgreSQL 数据库"""
#     try:
#         conn = psycopg2.connect(
#             host=DB_HOST,
#             database=DB_NAME,
#             user=DB_USER,
#             password=DB_PASSWORD,
#             port=DB_PORT
#         )
#         return conn
#     except psycopg2.Error as e:
#         print(f"Error connecting to the database: {e}")
#         return None

# def fetch_labels_from_db(conn, task_id):
#     """从数据库中获取指定 task_id 的标签数据"""
#     if conn is None:
#         return []
#     try:
#         cursor = conn.cursor()
#         query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {TABLE_NAME} WHERE task_id = %s"
#         cursor.execute(query, (task_id,))
#         labels_data = cursor.fetchall()
#         cursor.close()
#         return labels_data
#     except psycopg2.Error as e:
#         print(f"Error fetching labels from database: {e}")
#         return []

# def delete_existing_results_db(conn, task_id):
#     """删除数据库中指定 task_id 的原有数据"""
#     if conn is None:
#         return
#     cursor = conn.cursor()
#     try:
#         delete_query = f"DELETE FROM {TABLE_NAME} WHERE task_id = %s"
#         cursor.execute(delete_query, (task_id,))
#         conn.commit()
#         print(f"已删除 task_id {task_id} 的原有数据。")
#     except psycopg2.Error as e:
#         print(f"Error deleting existing results from database: {e}")
#         conn.rollback()
#     finally:
#         cursor.close()

# def insert_segmentation_results_db(conn, task_id, detection_polygons, user_id, status):
#     """将检测结果写入数据库，使用原始坐标字符串格式"""
#     if conn is None:
#         return
#     cursor = conn.cursor()
#     insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s"

#     values_list = []
#     for type_id, polygons in detection_polygons.items():
#         for polygon in polygons:
#             geom_str = ', '.join([f"{x}, {y}" for x, y in polygon.exterior.coords])
#             values_list.append((cursor.mogrify("(%s, %s, %s, %s, %s)", 
#                                               (geom_str, int(type_id), user_id, task_id, status)).decode('utf-8')))

#     if values_list:
#         values_str = ','.join(values_list)
#         full_insert_query = insert_query % values_str
#         try:
#             cursor.execute(full_insert_query)
#             conn.commit()
#             print(f"检测结果已成功写入数据库 task_id {task_id}，使用 user_id: {user_id}")
#         except Exception as e:
#             conn.rollback()
#             print(f"写入数据库时出错: {e}")
#     else:
#         print("没有生成任何检测多边形，未写入数据库。")

#     cursor.close()

# # -------------------- 图像转换函数 --------------------
# def convert_tif_to_jpeg(tif_path, output_jpeg_path):
#     """将 .tif 文件转换为 RGB JPEG 文件，仅保留前三个波段"""
#     try:
#         with rasterio.open(tif_path) as src:
#             if src.count < 3:
#                 raise ValueError(f"图像 {tif_path} 的波段数少于 3，无法转换为 RGB JPEG")
            
#             img = src.read([1, 2, 3])
#             img = np.transpose(img, (1, 2, 0))

#             if img.dtype != np.uint8:
#                 img = img.astype(np.float32)
#                 img_min, img_max = img.min(), img.max()
#                 if img_max > img_min:
#                     img = (img - img_min) / (img_max - img_min) * 255
#                 img = img.astype(np.uint8)

#             image = Image.fromarray(img, mode='RGB')
#             image.save(output_jpeg_path, format='JPEG', quality=95)
#             print(f"成功将 {tif_path} 转换为 {output_jpeg_path}")
#             return True
#     except Exception as e:
#         print(f"转换 {tif_path} 到 JPEG 时出错: {e}")
#         return False

# # -------------------- 可视化函数 --------------------
# def draw_boxes_on_image(image_path, boxes, labels, output_path, color=(0, 255, 0)):
#     """在图像上绘制 bounding boxes"""
#     img = cv2.imread(image_path)
#     if img is None:
#         print(f"无法加载图像 {image_path}")
#         return

#     for box, label in zip(boxes, labels):
#         x1, y1, x2, y2 = box
#         x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
#         cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
#         cv2.putText(img, str(label), (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

#     cv2.imwrite(output_path, img)
#     print(f"已保存可视化图像到 {output_path}")

# # -------------------- YOLO 数据集生成函数 --------------------
# def create_yolo_dataset(labels_data, image_path, output_dir):
#     """从数据库提取标注，生成 YOLO 格式的数据集，并返回标注框用于可视化"""
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     images_dir = os.path.join(output_dir, "images")
#     labels_dir = os.path.join(output_dir, "labels")
#     os.makedirs(images_dir, exist_ok=True)
#     os.makedirs(labels_dir, exist_ok=True)

#     image_name = os.path.basename(image_path)
#     jpeg_name = image_name.replace(".tif", ".jpg")
#     jpeg_path = os.path.join(images_dir, jpeg_name)
#     if not convert_tif_to_jpeg(image_path, jpeg_path):
#         raise ValueError(f"无法将 {image_path} 转换为 JPEG，程序退出。")

#     with Image.open(jpeg_path) as img:
#         img_width, img_height = img.size

#     with rasterio.open(image_path) as src:
#         inverse_transform = ~src.transform
#         tif_width, tif_height = src.width, src.height
#         tif_crs = src.crs
#         if tif_crs != CRS.from_epsg(3857):
#             print(f"警告: 图像坐标系为 {tif_crs}，不是 EPSG:3857，可能导致坐标转换错误！")

#     width_ratio = img_width / tif_width
#     height_ratio = img_height / tif_height

#     label_file_path = os.path.join(labels_dir, jpeg_name.replace(".jpg", ".txt"))
#     type_id_to_class_id = {}
#     class_id_counter = 0
#     original_boxes = []
#     original_labels = []

#     with open(label_file_path, "w") as f:
#         for _, geom_str, type_id, *_ in labels_data:
#             try:
#                 if type_id not in type_id_to_class_id:
#                     type_id_to_class_id[type_id] = class_id_counter
#                     class_id_counter += 1
#                 class_id = type_id_to_class_id[type_id]

#                 coords_str_list = geom_str.split(',')
#                 coords_list = []
#                 for i in range(0, len(coords_str_list), 2):
#                     x = float(coords_str_list[i].strip())
#                     y = float(coords_str_list[i + 1].strip())
#                     coords_list.append((x, y))

#                 polygon = Polygon(coords_list)
#                 minx, miny, maxx, maxy = polygon.bounds

#                 pixel_minx, pixel_miny = inverse_transform * (minx, miny)
#                 pixel_maxx, pixel_maxy = inverse_transform * (maxx, maxy)

#                 pixel_minx *= width_ratio
#                 pixel_maxx *= width_ratio
#                 pixel_miny *= height_ratio
#                 pixel_maxy *= height_ratio

#                 x_center = (pixel_minx + pixel_maxx) / 2
#                 y_center = (pixel_miny + pixel_maxy) / 2
#                 width = abs(pixel_maxx - pixel_minx)
#                 height = abs(pixel_maxy - pixel_miny)

#                 x_center_norm = x_center / img_width
#                 y_center_norm = y_center / img_height
#                 width_norm = width / img_width
#                 height_norm = height / img_height

#                 x_center_norm = max(0, min(x_center_norm, 1))
#                 y_center_norm = max(0, min(y_center_norm, 1))
#                 width_norm = max(0, min(width_norm, 1))
#                 height_norm = max(0, min(height_norm, 1))

#                 f.write(f"{class_id} {x_center_norm} {y_center_norm} {width_norm} {height_norm}\n")

#                 x1 = (x_center - width / 2)
#                 y1 = (y_center - height / 2)
#                 x2 = (x_center + width / 2)
#                 y2 = (y_center + height / 2)
#                 original_boxes.append([x1, y1, x2, y2])
#                 original_labels.append(f"Class {class_id}")

#             except Exception as e:
#                 print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
#                 continue

#     return images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels

# def create_yolo_data_yaml(output_dir, images_dir, labels_dir, type_ids):
#     """生成 YOLO 数据集的 data.yaml 文件"""
#     data_yaml_path = os.path.join(output_dir, "data.yaml")
#     with open(data_yaml_path, "w") as f:
#         f.write("train: {}\n".format(os.path.join(images_dir, "train")))
#         f.write("val: {}\n".format(os.path.join(images_dir, "val")))
#         f.write("nc: {}\n".format(len(type_ids)))
#         f.write("names: {}\n".format([str(i) for i in range(len(type_ids))]))
#     return data_yaml_path

# # -------------------- 处理 YOLO 检测结果 --------------------
# def process_yolo_results(results, transform, task_id, user_id, status, conn, class_id_to_type_id, output_image_path):
#     """处理 YOLO 检测结果，将 bounding box 转换为地理坐标并插入数据库，并返回检测框用于可视化"""
#     if not results or len(results) == 0:
#         print("YOLO 检测未返回有效结果！")
#         return {}, [], []

#     detection_polygons = {}
#     detection_boxes = []
#     detection_labels = []

#     for result in results:
#         if result.boxes is None or len(result.boxes) == 0:
#             print("无检测结果！")
#             continue

#         boxes = result.boxes.xyxy.cpu().numpy()
#         class_ids = result.boxes.cls.cpu().numpy()
#         confidences = result.boxes.conf.cpu().numpy()

#         print(f"检测到 {len(boxes)} 个目标框:")
#         print(f"所有检测框置信度: {confidences}")
#         for i, (box, class_id, conf) in enumerate(zip(boxes, class_ids, confidences)):
#             print(f"目标 {i+1}: class_id={int(class_id)}, conf={conf:.3f}, box={box}")

#             type_id = class_id_to_type_id.get(int(class_id))
#             if type_id is None:
#                 print(f"警告: class_id {class_id} 未找到对应的 type_id，跳过。")
#                 continue

#             x1, y1, x2, y2 = box

#             with Image.open(result.path) as img:
#                 img_width, img_height = img.size
#             with rasterio.open(IMAGE_PATH) as src:
#                 tif_width, tif_height = src.width, src.height
#             width_ratio = tif_width / img_width
#             height_ratio = tif_height / img_height

#             x1_tif = x1 * width_ratio
#             x2_tif = x2 * width_ratio
#             y1_tif = y1 * height_ratio
#             y2_tif = y2 * height_ratio

#             corners = [
#                 (x1_tif, y1_tif),
#                 (x2_tif, y1_tif),
#                 (x2_tif, y2_tif),
#                 (x1_tif, y2_tif),
#                 (x1_tif, y1_tif)
#             ]
#             geo_corners = [(transform * (x, y)) for x, y in corners]
#             geo_corners = [(float(x), float(y)) for x, y in geo_corners]

#             if type_id not in detection_polygons:
#                 detection_polygons[type_id] = []
#             polygon = Polygon(geo_corners)
#             detection_polygons[type_id].append(polygon)

#             detection_boxes.append([x1, y1, x2, y2])
#             detection_labels.append(f"Class {class_id} (conf: {conf:.2f})")

#     return detection_polygons, detection_boxes, detection_labels

# # -------------------- 清理函数 --------------------
# def cleanup_training_files(output_dir):
#     """删除生成的训练文件目录"""
#     try:
#         if os.path.exists(output_dir):
#             shutil.rmtree(output_dir)
#             print(f"已删除训练目录: {output_dir}")
#         else:
#             print(f"训练目录 {output_dir} 不存在，无需删除。")
#     except Exception as e:
#         print(f"删除训练目录 {output_dir} 时出错: {e}")

# # -------------------- 主函数 --------------------
# def main():
#     global IMAGE_PATH
#     # 任务参数
#     TASK_ID = 128
#     IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"

#     # 训练参数
#     NUM_EPOCHS = 50
#     CONF_THRESHOLD = 0.5  # 进一步降低置信度阈值

#     # 检查 GPU 是否可用
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"Using device: {device}")

#     # 连接数据库
#     conn = connect_db()
#     if conn is None:
#         print("无法连接到数据库，程序退出。")
#         return

#     # 获取原始标签数据
#     labels_data = fetch_labels_from_db(conn, TASK_ID)
#     if not labels_data:
#         print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
#         conn.close()
#         return

#     user_ids = set(row[3] for row in labels_data)
#     if len(user_ids) > 1:
#         print(f"警告: task_id {TASK_ID} 包含多个 user_id: {user_ids}，使用第一个")
#     user_id = labels_data[0][3]
#     status = labels_data[0][5]

#     type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
#     if not type_ids_from_db:
#         print("没有有效的 type_id，请检查数据库中的标注数据。")
#         conn.close()
#         return

#     # 创建 YOLO 数据集并获取原始标注框
#     output_dir = os.path.join(os.getcwd(), "yolo_dataset")
#     images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels = create_yolo_dataset(labels_data, IMAGE_PATH, output_dir)

#     class_id_to_type_id = {v: k for k, v in type_id_to_class_id.items()}
#     print(f"type_id 到 class_id 映射: {type_id_to_class_id}")
#     print(f"class_id 到 type_id 映射: {class_id_to_type_id}")

#     os.makedirs(os.path.join(images_dir, "train"), exist_ok=True)
#     os.makedirs(os.path.join(images_dir, "val"), exist_ok=True)
#     os.makedirs(os.path.join(labels_dir, "train"), exist_ok=True)
#     os.makedirs(os.path.join(labels_dir, "val"), exist_ok=True)

#     image_name = os.path.basename(jpeg_path)
#     label_name = image_name.replace(".jpg", ".txt")
#     for split in ["train", "val"]:
#         shutil.copy(os.path.join(images_dir, image_name),
#                     os.path.join(images_dir, split, image_name))
#         shutil.copy(os.path.join(labels_dir, label_name),
#                     os.path.join(labels_dir, split, label_name))

#     data_yaml_path = create_yolo_data_yaml(output_dir, images_dir, labels_dir, type_ids_from_db)

#     # 可视化原始标注框
#     original_output_path = os.path.join(output_dir, "original_with_boxes.jpg")
#     draw_boxes_on_image(jpeg_path, original_boxes, original_labels, original_output_path, color=(0, 255, 0))

#     # 初始化 YOLO 模型
#     model = YOLO("yolo11m-obb.pt")

#     # 训练 YOLO 模型
#     train_results = model.train(
#         data=data_yaml_path,
#         epochs=NUM_EPOCHS,
#         imgsz=1280,  # 增大输入尺寸以保留更多细节
#         device=device
#     )

#     with rasterio.open(IMAGE_PATH) as src:
#         original_transform = src.transform

#     # 进行目标检测
#     inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
#     results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=1280, save=True, save_txt=True)

#     # 处理 YOLO 检测结果
#     detection_polygons, detection_boxes, detection_labels = process_yolo_results(
#         results, original_transform, TASK_ID, user_id, status, conn, class_id_to_type_id, inference_output_path
#     )

#     # 可视化推理结果
#     if detection_boxes:
#         draw_boxes_on_image(jpeg_path, detection_boxes, detection_labels, inference_output_path, color=(255, 0, 0))
#     else:
#         shutil.copy(jpeg_path, inference_output_path)
#         print("无检测结果，保存原始图像作为推理结果可视化")

#     # 删除数据库中旧的检测结果
#     delete_existing_results_db(conn, TASK_ID)

#     # 将新结果写入数据库
#     insert_segmentation_results_db(conn, TASK_ID, detection_polygons, user_id, status)

#     # 写入数据库后，删除训练文件
#     # cleanup_training_files(output_dir)

#     # 关闭数据库连接
#     conn.close()
#     print("任务完成!")

# if __name__ == "__main__":
#     main()

import os
import psycopg2
import rasterio
import numpy as np
from shapely.geometry import Polygon
from ultralytics import YOLO
import shutil
import torch
from PIL import Image
import cv2
from rasterio.crs import CRS

# 数据库连接信息 (请替换为你的实际信息)
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"
TABLE_NAME2 = "task"

# -------------------- 数据库操作函数 --------------------
# (Keeping these unchanged as they are fine)
def connect_db():
    """连接到 PostgreSQL 数据库"""
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

def insert_segmentation_results_db(conn, task_id, detection_polygons, user_id, status):
    """将检测结果写入数据库，使用原始坐标字符串格式"""
    if conn is None:
        return
    cursor = conn.cursor()
    insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s"

    values_list = []
    for type_id, polygons in detection_polygons.items():
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
            print(f"检测结果已成功写入数据库 task_id {task_id}，使用 user_id: {user_id}")
        except Exception as e:
            conn.rollback()
            print(f"写入数据库时出错: {e}")
    else:
        print("没有生成任何检测多边形，未写入数据库。")

    cursor.close()

# -------------------- 图像转换函数 --------------------
def convert_tif_to_jpeg(tif_path, output_jpeg_path):
    """将 .tif 文件转换为 RGB JPEG 文件，仅保留前三个波段"""
    try:
        with rasterio.open(tif_path) as src:
            if src.count < 3:
                raise ValueError(f"图像 {tif_path} 的波段数少于 3，无法转换为 RGB JPEG")
            
            img = src.read([1, 2, 3])
            img = np.transpose(img, (1, 2, 0))

            if img.dtype != np.uint8:
                img = img.astype(np.float32)
                img_min, img_max = img.min(), img.max()
                if img_max > img_min:
                    img = (img - img_min) / (img_max - img_min) * 255
                img = img.astype(np.uint8)

            image = Image.fromarray(img, mode='RGB')
            image.save(output_jpeg_path, format='JPEG', quality=95)
            print(f"成功将 {tif_path} 转换为 {output_jpeg_path}")
            return True
    except Exception as e:
        print(f"转换 {tif_path} 到 JPEG 时出错: {e}")
        return False

# -------------------- 可视化函数 --------------------
def draw_boxes_on_image(image_path, boxes, labels, output_path, color=(0, 255, 0)):
    """在图像上绘制 bounding boxes"""
    img = cv2.imread(image_path)
    if img is None:
        print(f"无法加载图像 {image_path}")
        return

    for box, label in zip(boxes, labels):
        if len(box) == 4:  # Regular bounding box
            x1, y1, x2, y2 = box
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        elif len(box) == 8:  # OBB (x1, y1, x2, y2, x3, y3, x4, y4)
            points = np.array(box, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [points], isClosed=True, color=color, thickness=2)
        cv2.putText(img, str(label), (int(box[0]), int(box[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.imwrite(output_path, img)
    print(f"已保存可视化图像到 {output_path}")

# -------------------- YOLO 数据集生成函数 --------------------
def create_yolo_dataset(labels_data, image_path, output_dir):
    """从数据库提取标注，生成 YOLO OBB 格式的数据集，并返回标注框用于可视化"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    images_dir = os.path.join(output_dir, "images")
    labels_dir = os.path.join(output_dir, "labels")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)

    image_name = os.path.basename(image_path)
    jpeg_name = image_name.replace(".tif", ".jpg")
    jpeg_path = os.path.join(images_dir, jpeg_name)
    if not convert_tif_to_jpeg(image_path, jpeg_path):
        raise ValueError(f"无法将 {image_path} 转换为 JPEG，程序退出。")

    with Image.open(jpeg_path) as img:
        img_width, img_height = img.size

    with rasterio.open(image_path) as src:
        inverse_transform = ~src.transform
        tif_width, tif_height = src.width, src.height
        tif_crs = src.crs
        if tif_crs != CRS.from_epsg(3857):
            print(f"警告: 图像坐标系为 {tif_crs}，不是 EPSG:3857，可能导致坐标转换错误！")

    width_ratio = img_width / tif_width
    height_ratio = img_height / tif_height

    label_file_path = os.path.join(labels_dir, jpeg_name.replace(".jpg", ".txt"))
    type_id_to_class_id = {}
    class_id_counter = 0
    original_boxes = []
    original_labels = []

    with open(label_file_path, "w") as f:
        for _, geom_str, type_id, *_ in labels_data:
            try:
                if type_id not in type_id_to_class_id:
                    type_id_to_class_id[type_id] = class_id_counter
                    class_id_counter += 1
                class_id = type_id_to_class_id[type_id]

                coords_str_list = geom_str.split(',')
                coords_list = []
                for i in range(0, len(coords_str_list), 2):
                    x = float(coords_str_list[i].strip())
                    y = float(coords_str_list[i + 1].strip())
                    coords_list.append((x, y))

                polygon = Polygon(coords_list)
                coords = list(polygon.exterior.coords)[:-1]  # Remove duplicate closing point

                # Convert to pixel coordinates
                pixel_coords = [inverse_transform * (x, y) for x, y in coords]
                pixel_coords = [(x * width_ratio, y * height_ratio) for x, y in pixel_coords]

                # Ensure we have at least 4 points for a valid OBB
                if len(pixel_coords) < 4:
                    print(f"警告: 多边形点数少于4，跳过: {geom_str}")
                    continue

                # Normalize coordinates to [0, 1]
                norm_coords = [(x / img_width, y / img_height) for x, y in pixel_coords[:4]]  # Take first 4 points for OBB
                norm_coords = [max(0, min(1, coord)) for sublist in norm_coords for coord in sublist]  # Flatten and clamp

                # Write in YOLO OBB format: class_id x1 y1 x2 y2 x3 y3 x4 y4
                f.write(f"{class_id} {' '.join(map(str, norm_coords))}\n")

                # For visualization (use pixel coordinates)
                obb_box = [coord for point in pixel_coords[:4] for coord in point]  # Flatten to [x1, y1, x2, y2, x3, y3, x4, y4]
                original_boxes.append(obb_box)
                original_labels.append(f"Class {class_id}")

            except Exception as e:
                print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
                continue

    return images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels

def create_yolo_data_yaml(output_dir, images_dir, labels_dir, type_ids):
    """生成 YOLO 数据集的 data.yaml 文件"""
    data_yaml_path = os.path.join(output_dir, "data.yaml")
    with open(data_yaml_path, "w") as f:
        f.write("train: {}\n".format(os.path.join(images_dir, "train")))
        f.write("val: {}\n".format(os.path.join(images_dir, "val")))
        f.write("nc: {}\n".format(len(type_ids)))
        f.write("names: {}\n".format([str(i) for i in range(len(type_ids))]))
    return data_yaml_path

# -------------------- 处理 YOLO 检测结果 --------------------
def process_yolo_results(results, transform, task_id, user_id, status, conn, class_id_to_type_id, output_image_path):
    """处理 YOLO OBB 检测结果，将检测框转换为地理坐标并插入数据库"""
    if not results or len(results) == 0:
        print("YOLO 检测未返回有效结果！")
        return {}, [], []

    detection_polygons = {}
    detection_boxes = []
    detection_labels = []

    for result in results:
        if result.obb is None or len(result.obb.xyxyxyxy) == 0:
            print("无 OBB 检测结果！")
            continue

        boxes = result.obb.xyxyxyxy.cpu().numpy()  # OBB coordinates (x1, y1, x2, y2, x3, y3, x4, y4)
        class_ids = result.obb.cls.cpu().numpy()
        confidences = result.obb.conf.cpu().numpy()

        print(f"检测到 {len(boxes)} 个 OBB 目标框:")
        print(f"所有检测框置信度: {confidences}")
        for i, (box, class_id, conf) in enumerate(zip(boxes, class_ids, confidences)):
            print(f"目标 {i+1}: class_id={int(class_id)}, conf={conf:.3f}, box={box}")

            type_id = class_id_to_type_id.get(int(class_id))
            if type_id is None:
                print(f"警告: class_id {class_id} 未找到对应的 type_id，跳过。")
                continue

            with Image.open(result.path) as img:
                img_width, img_height = img.size
            with rasterio.open(IMAGE_PATH) as src:
                tif_width, tif_height = src.width, src.height
            width_ratio = tif_width / img_width
            height_ratio = tif_height / img_height

            # Convert to tif coordinates
            tif_coords = [(x * width_ratio, y * height_ratio) for x, y in box.reshape(4, 2)]
            geo_corners = [(transform * (x, y)) for x, y in tif_coords]
            geo_corners = [(float(x), float(y)) for x, y in geo_corners]

            if type_id not in detection_polygons:
                detection_polygons[type_id] = []
            polygon = Polygon(geo_corners)
            detection_polygons[type_id].append(polygon)

            detection_boxes.append(box.flatten().tolist())  # Flatten to [x1, y1, x2, y2, x3, y3, x4, y4]
            detection_labels.append(f"Class {class_id} (conf: {conf:.2f})")

    return detection_polygons, detection_boxes, detection_labels

# -------------------- 清理函数 --------------------
def cleanup_training_files(output_dir):
    """删除生成的训练文件目录"""
    try:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            print(f"已删除训练目录: {output_dir}")
        else:
            print(f"训练目录 {output_dir} 不存在，无需删除。")
    except Exception as e:
        print(f"删除训练目录 {output_dir} 时出错: {e}")

# -------------------- 主函数 --------------------
def main():
    global IMAGE_PATH
    # 任务参数
    TASK_ID = 128
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"

    # 训练参数
    NUM_EPOCHS = 50
    CONF_THRESHOLD = 0.5

    # 检查 GPU 是否可用
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

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

    user_ids = set(row[3] for row in labels_data)
    if len(user_ids) > 1:
        print(f"警告: task_id {TASK_ID} 包含多个 user_id: {user_ids}，使用第一个")
    user_id = labels_data[0][3]
    status = labels_data[0][5]

    type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
    if not type_ids_from_db:
        print("没有有效的 type_id，请检查数据库中的标注数据。")
        conn.close()
        return

    # 创建 YOLO 数据集并获取原始标注框
    output_dir = os.path.join(os.getcwd(), "yolo_dataset")
    images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels = create_yolo_dataset(labels_data, IMAGE_PATH, output_dir)

    class_id_to_type_id = {v: k for k, v in type_id_to_class_id.items()}
    print(f"type_id 到 class_id 映射: {type_id_to_class_id}")
    print(f"class_id 到 type_id 映射: {class_id_to_type_id}")

    os.makedirs(os.path.join(images_dir, "train"), exist_ok=True)
    os.makedirs(os.path.join(images_dir, "val"), exist_ok=True)
    os.makedirs(os.path.join(labels_dir, "train"), exist_ok=True)
    os.makedirs(os.path.join(labels_dir, "val"), exist_ok=True)

    image_name = os.path.basename(jpeg_path)
    label_name = image_name.replace(".jpg", ".txt")
    for split in ["train", "val"]:
        shutil.copy(os.path.join(images_dir, image_name),
                    os.path.join(images_dir, split, image_name))
        shutil.copy(os.path.join(labels_dir, label_name),
                    os.path.join(labels_dir, split, label_name))

    data_yaml_path = create_yolo_data_yaml(output_dir, images_dir, labels_dir, type_ids_from_db)

    # 可视化原始标注框
    original_output_path = os.path.join(output_dir, "original_with_boxes.jpg")
    draw_boxes_on_image(jpeg_path, original_boxes, original_labels, original_output_path, color=(0, 255, 0))

    # 初始化 YOLO 模型 (改为 yolo11n-obb)
    model = YOLO("yolo11m-obb.pt")

    # 训练 YOLO 模型
    train_results = model.train(
        data=data_yaml_path,
        epochs=NUM_EPOCHS,
        imgsz=1024,
        device=device
    )

    with rasterio.open(IMAGE_PATH) as src:
        original_transform = src.transform

    # 进行目标检测
    inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
    results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=1024, save=True, save_txt=True)

    # 处理 YOLO 检测结果
    detection_polygons, detection_boxes, detection_labels = process_yolo_results(
        results, original_transform, TASK_ID, user_id, status, conn, class_id_to_type_id, inference_output_path
    )

    # 可视化推理结果
    if detection_boxes:
        draw_boxes_on_image(jpeg_path, detection_boxes, detection_labels, inference_output_path, color=(255, 0, 0))
    else:
        shutil.copy(jpeg_path, inference_output_path)
        print("无检测结果，保存原始图像作为推理结果可视化")

    # 删除数据库中旧的检测结果
    delete_existing_results_db(conn, TASK_ID)

    # 将新结果写入数据库
    insert_segmentation_results_db(conn, TASK_ID, detection_polygons, user_id, status)

    # 写入数据库后，删除训练文件
    # cleanup_training_files(output_dir)

    # 关闭数据库连接
    conn.close()
    print("任务完成!")

if __name__ == "__main__":
    main()