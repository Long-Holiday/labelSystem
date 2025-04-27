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

# # -------------------- 计算 IoU 函数 --------------------
# def compute_iou(box1, box2):
#     """计算两个 bounding box 的 IoU"""
#     x1_1, y1_1, x2_1, y2_1 = box1
#     x1_2, y1_2, x2_2, y2_2 = box2

#     x1_i = max(x1_1, x1_2)
#     y1_i = max(y1_1, y1_2)
#     x2_i = min(x2_1, x2_2)
#     y2_i = min(y2_1, y2_2)

#     inter_area = max(0, x2_i - x1_i) * max(0, y2_i - y1_i)

#     box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
#     box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
#     union_area = box1_area + box2_area - inter_area

#     iou = inter_area / union_area if union_area > 0 else 0
#     return iou

# # -------------------- 提取标注框并映射类别 --------------------
# def extract_boxes_and_map_classes(labels_data, yolo_results, image_path, output_dir):
#     """提取手动标注框，并映射到预训练 YOLO 的类别"""
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     images_dir = os.path.join(output_dir, "images")
#     os.makedirs(images_dir, exist_ok=True)

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

#     # 提取手动标注框
#     manual_boxes = []
#     manual_labels = []
#     type_id_to_manual_boxes = {}

#     for _, geom_str, type_id, *_ in labels_data:
#         try:
#             coords_str_list = geom_str.split(',')
#             coords_list = []
#             for i in range(0, len(coords_str_list), 2):
#                 x = float(coords_str_list[i].strip())
#                 y = float(coords_str_list[i + 1].strip())
#                 coords_list.append((x, y))

#             polygon = Polygon(coords_list)
#             minx, miny, maxx, maxy = polygon.bounds

#             pixel_minx, pixel_miny = inverse_transform * (minx, miny)
#             pixel_maxx, pixel_maxy = inverse_transform * (maxx, maxy)

#             pixel_minx *= width_ratio
#             pixel_maxx *= width_ratio
#             pixel_miny *= height_ratio
#             pixel_maxy *= height_ratio

#             x1 = pixel_minx
#             y1 = pixel_miny
#             x2 = pixel_maxx
#             y2 = pixel_maxy
#             box = [x1, y1, x2, y2]

#             manual_boxes.append(box)
#             manual_labels.append(f"Type {type_id}")

#             if type_id not in type_id_to_manual_boxes:
#                 type_id_to_manual_boxes[type_id] = []
#             type_id_to_manual_boxes[type_id].append(box)

#         except Exception as e:
#             print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
#             continue

#     # 获取 YOLO 预训练模型的检测结果
#     yolo_boxes = []
#     yolo_class_ids = []
#     yolo_confidences = []
#     for result in yolo_results:
#         if result.boxes is None or len(result.boxes) == 0:
#             continue

#         boxes = result.boxes.xyxy.cpu().numpy()
#         class_ids = result.boxes.cls.cpu().numpy()
#         confidences = result.boxes.conf.cpu().numpy()

#         yolo_boxes.extend(boxes)
#         yolo_class_ids.extend(class_ids)
#         yolo_confidences.extend(confidences)

#     # 建立 type_id 到 class_id 的映射
#     type_id_to_class_id = {}
#     assigned_class_ids = set()  # 用于确保一对一映射
#     for type_id, boxes in type_id_to_manual_boxes.items():
#         max_iou = 0
#         best_class_id = None
#         for manual_box in boxes:
#             for yolo_box, class_id in zip(yolo_boxes, yolo_class_ids):
#                 iou = compute_iou(manual_box, yolo_box)
#                 if iou > max_iou and int(class_id) not in assigned_class_ids:
#                     max_iou = iou
#                     best_class_id = int(class_id)
#         if best_class_id is not None:
#             type_id_to_class_id[type_id] = best_class_id
#             assigned_class_ids.add(best_class_id)
#             print(f"手动类别 type_id={type_id} 映射到预训练类别 class_id={best_class_id}，最大 IoU={max_iou:.3f}")
#         else:
#             print(f"手动类别 type_id={type_id} 未找到未分配的匹配预训练类别，跳过")

#     return jpeg_path, manual_boxes, manual_labels, type_id_to_class_id

# # -------------------- 处理 YOLO 检测结果并映射类别 --------------------
# def process_yolo_results(results, transform, task_id, user_id, status, conn, type_id_to_class_id, output_image_path):
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

#             # 查找对应的 type_id
#             type_id = None
#             for t_id, c_id in type_id_to_class_id.items():
#                 if int(class_id) == c_id:
#                     type_id = t_id
#                     break

#             if type_id is None:
#                 print(f"预训练类别 class_id={class_id} 未匹配到任何手动类别，跳过")
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
#             detection_labels.append(f"Type {type_id} (conf: {conf:.2f})")

#     return detection_polygons, detection_boxes, detection_labels

# # -------------------- 主函数 --------------------
# def main():
#     global IMAGE_PATH
#     # 任务参数
#     TASK_ID = 128
#     IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"

#     # 推理参数
#     CONF_THRESHOLD = 0.03  # 降低置信度阈值

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

#     # 初始化 YOLO 预训练模型 并 先推理
#     model = YOLO("yolo11n.pt")
#     output_dir = os.path.join(os.getcwd(), "yolo_dataset")
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     image_name = os.path.basename(IMAGE_PATH)
#     jpeg_name = image_name.replace(".tif", ".jpg")
#     images_dir = os.path.join(output_dir, "images")
#     os.makedirs(images_dir, exist_ok=True)
#     jpeg_path = os.path.join(images_dir, jpeg_name)
#     if not convert_tif_to_jpeg(IMAGE_PATH, jpeg_path):
#         raise ValueError(f"无法将 {IMAGE_PATH} 转换为 JPEG，程序退出。")

#     results = model.predict(source=jpeg_path, conf=CONF_THRESHOLD, imgsz=1280, save=True, save_txt=True)

#     # 提取原始标注框并映射类别
#     _, manual_boxes, manual_labels, type_id_to_class_id = extract_boxes_and_map_classes(labels_data, results, IMAGE_PATH, output_dir)

#     # 可视化原始标注框
#     original_output_path = os.path.join(output_dir, "original_with_boxes.jpg")
#     draw_boxes_on_image(jpeg_path, manual_boxes, manual_labels, original_output_path, color=(0, 255, 0))

#     # 进行目标检测
#     with rasterio.open(IMAGE_PATH) as src:
#         original_transform = src.transform
#         tif_crs = src.crs
#         if tif_crs != CRS.from_epsg(3857):
#             print(f"警告: 图像坐标系为 {tif_crs}，不是 EPSG:3857，可能导致坐标转换错误！")

#     inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
#     # results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=1280, save=True, save_txt=True)

#     # 处理 YOLO 检测结果
#     detection_polygons, detection_boxes, detection_labels = process_yolo_results(
#         results, original_transform, TASK_ID, user_id, status, conn, type_id_to_class_id, inference_output_path
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
        x1, y1, x2, y2 = box
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, str(label), (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.imwrite(output_path, img)
    print(f"已保存可视化图像到 {output_path}")

# -------------------- 计算 IoU 函数 --------------------
def compute_iou(box1, box2):
    """计算两个 bounding box 的 IoU"""
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2

    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y1_2, y2_1)  # Corrected this line: y2_i = min(y2_1, y2_2) -> y2_i = min(y1_2, y2_1) to y2_i = min(y2_1, y2_2) and y1_i = max(y1_1, y1_2) to y1_i = max(y1_1, y1_2) and x2_i = min(x2_1, x2_2) to x2_i = min(x2_1, x2_2) and x1_i = max(x1_1, x1_2) to x1_i = max(x1_1, x1_2) and y2_i = min(y2_1, y2_2) to y2_i = min(y2_1, y2_2) and  y1_i = max(y1_1, y1_2) to y1_i = max(y1_1, y1_2)

    y2_i = min(y2_1, y2_2)

    inter_area = max(0, x2_i - x1_i) * max(0, y2_i - y1_i)

    box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = box1_area + box2_area - inter_area

    iou = inter_area / union_area if union_area > 0 else 0
    return iou

# -------------------- 提取标注框并映射类别 --------------------
def extract_boxes_and_map_classes(labels_data, yolo_results, image_path, output_dir):
    """提取手动标注框，并映射到预训练 YOLO 的类别"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

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

    # 提取手动标注框
    manual_boxes = []
    manual_labels = []
    type_id_to_manual_boxes = {}

    print("\n----- Manual Boxes -----") # Debugging print
    for _, geom_str, type_id, *_ in labels_data:
        try:
            coords_str_list = geom_str.split(',')
            coords_list = []
            for i in range(0, len(coords_str_list), 2):
                x = float(coords_str_list[i].strip())
                y = float(coords_str_list[i + 1].strip())
                coords_list.append((x, y))

            polygon = Polygon(coords_list)
            minx, miny, maxx, maxy = polygon.bounds

            pixel_minx, pixel_miny = inverse_transform * (minx, miny)
            pixel_maxx, pixel_maxy = inverse_transform * (maxx, maxy)

            pixel_minx *= width_ratio
            pixel_maxx *= width_ratio
            pixel_miny *= height_ratio
            pixel_maxy *= height_ratio

            x1 = pixel_minx
            y1 = pixel_miny
            x2 = pixel_maxx
            y2 = pixel_maxy
            box = [x1, y1, x2, y2]

            manual_boxes.append(box)
            manual_labels.append(f"Type {type_id}")

            if type_id not in type_id_to_manual_boxes:
                type_id_to_manual_boxes[type_id] = []
            type_id_to_manual_boxes[type_id].append(box)
            print(f"Manual Box Type {type_id}: {box}") # Debugging print

        except Exception as e:
            print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
            continue

    # 获取 YOLO 预训练模型的检测结果
    yolo_boxes = []
    yolo_class_ids = []
    yolo_confidences = []
    print("\n----- YOLO Results -----") # Debugging print
    for result in yolo_results:
        if result.boxes is None or len(result.boxes) == 0:
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()

        yolo_boxes.extend(boxes)
        yolo_class_ids.extend(class_ids)
        yolo_confidences.extend(confidences)

        for i in range(len(boxes)): # Debugging print
            print(f"YOLO Box {i}: Box={boxes[i]}, Class_id={class_ids[i]}, Confidence={confidences[i]:.2f}") # Debugging print


    # 建立 type_id 到 class_id 的映射
    type_id_to_class_id = {}
    assigned_class_ids = set()  # 用于确保一对一映射
    print("\n----- Type ID to Class ID Mapping -----") # Debugging print
    for type_id, boxes in type_id_to_manual_boxes.items():
        max_iou = 0
        best_class_id = None
        for manual_box in boxes:
            for i in range(len(yolo_boxes)): # Iterate with index for debugging
                yolo_box = yolo_boxes[i]
                class_id = yolo_class_ids[i]
                iou = compute_iou(manual_box, yolo_box)
                print(f"  IoU between Manual Box (Type {type_id}) {manual_box} and YOLO Box (Class {int(class_id)}) {yolo_box} = {iou:.3f}") # Debugging print
                if iou > max_iou and int(class_id) not in assigned_class_ids:
                    max_iou = iou
                    best_class_id = int(class_id)
        if best_class_id is not None:
            type_id_to_class_id[type_id] = best_class_id
            assigned_class_ids.add(best_class_id)
            print(f"手动类别 type_id={type_id} 映射到预训练类别 class_id={best_class_id}，最大 IoU={max_iou:.3f}")
        else:
            print(f"手动类别 type_id={type_id} 未找到未分配的匹配预训练类别，跳过")

    return jpeg_path, manual_boxes, manual_labels, type_id_to_class_id

# -------------------- 处理 YOLO 检测结果并映射类别 --------------------
def process_yolo_results(results, transform, task_id, user_id, status, conn, type_id_to_class_id, output_image_path):
    """处理 YOLO 检测结果，将 bounding box 转换为地理坐标并插入数据库，并返回检测框用于可视化"""
    if not results or len(results) == 0:
        print("YOLO 检测未返回有效结果！")
        return {}, [], []

    detection_polygons = {}
    detection_boxes = []
    detection_labels = []

    for result in results:
        if result.boxes is None or len(result.boxes) == 0:
            print("无检测结果！")
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()

        print(f"\n----- Processed Detections -----") # Debugging print
        print(f"检测到 {len(boxes)} 个目标框:")
        print(f"所有检测框置信度: {confidences}")
        for i, (box, class_id, conf) in enumerate(zip(boxes, class_ids, confidences)):
            print(f"目标 {i+1}: class_id={int(class_id)}, conf={conf:.3f}, box={box}")

            # 查找对应的 type_id
            type_id = None
            for t_id, c_id in type_id_to_class_id.items():
                if int(class_id) == c_id:
                    type_id = t_id
                    break

            if type_id is None:
                print(f"预训练类别 class_id={class_id} 未匹配到任何手动类别，跳过")
                continue

            x1, y1, x2, y2 = box

            with Image.open(result.path) as img:
                img_width, img_height = img.size
            with rasterio.open(IMAGE_PATH) as src:
                tif_width, tif_height = src.width, src.height
            width_ratio = tif_width / img_width
            height_ratio = tif_height / img_height

            x1_tif = x1 * width_ratio
            x2_tif = x2 * width_ratio
            y1_tif = y1 * height_ratio
            y2_tif = y2 * height_ratio

            corners = [
                (x1_tif, y1_tif),
                (x2_tif, y1_tif),
                (x2_tif, y2_tif),
                (x1_tif, y2_tif),
                (x1_tif, y1_tif)
            ]
            geo_corners = [(transform * (x, y)) for x, y in corners]
            geo_corners = [(float(x), float(y)) for x, y in geo_corners]

            if type_id not in detection_polygons:
                detection_polygons[type_id] = []
            polygon = Polygon(geo_corners)
            detection_polygons[type_id].append(polygon)

            detection_boxes.append([x1, y1, x2, y2])
            detection_labels.append(f"Type {type_id} (conf: {conf:.2f})")

    return detection_polygons, detection_boxes, detection_labels

# -------------------- 主函数 --------------------
def main():
    global IMAGE_PATH
    # 任务参数
    TASK_ID = 128
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"

    # 推理参数
    CONF_THRESHOLD = 0.03  # 降低置信度阈值

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

    # 初始化 YOLO 预训练模型 并 先推理
    model = YOLO("yolo11n.pt")
    output_dir = os.path.join(os.getcwd(), "yolo_dataset")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_name = os.path.basename(IMAGE_PATH)
    jpeg_name = image_name.replace(".tif", ".jpg")
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    jpeg_path = os.path.join(images_dir, jpeg_name)
    if not convert_tif_to_jpeg(IMAGE_PATH, jpeg_path):
        raise ValueError(f"无法将 {IMAGE_PATH} 转换为 JPEG，程序退出。")

    results = model.predict(source=jpeg_path, conf=CONF_THRESHOLD, imgsz=1280, save=True, save_txt=True)

    # 提取原始标注框并映射类别
    jpeg_path_extracted, manual_boxes, manual_labels, type_id_to_class_id = extract_boxes_and_map_classes(labels_data, results, IMAGE_PATH, output_dir)

    # 可视化原始标注框
    original_output_path = os.path.join(output_dir, "original_with_boxes.jpg")
    draw_boxes_on_image(jpeg_path_extracted, manual_boxes, manual_labels, original_output_path, color=(0, 255, 0))

    # 进行目标检测
    with rasterio.open(IMAGE_PATH) as src:
        original_transform = src.transform
        tif_crs = src.crs
        if tif_crs != CRS.from_epsg(3857):
            print(f"警告: 图像坐标系为 {tif_crs}，不是 EPSG:3857，可能导致坐标转换错误！")

    inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
    # results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=1280, save=True, save_txt=True) # No need to predict again, results are already available

    # 可视化 YOLO 检测框 (before mapping, for debugging)
    yolo_visual_path_before_mapping = os.path.join(output_dir, "yolo_detections_before_mapping.jpg")
    yolo_box_visual_before_mapping = []
    yolo_label_visual_before_mapping = []
    for result in results:
        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes.xyxy.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            for i in range(len(boxes)):
                yolo_box_visual_before_mapping.append(boxes[i])
                yolo_label_visual_before_mapping.append(f"Class {int(class_ids[i])} (conf: {confidences[i]:.2f})")
    draw_boxes_on_image(jpeg_path_extracted, yolo_box_visual_before_mapping, yolo_label_visual_before_mapping, yolo_visual_path_before_mapping, color=(255, 100, 0)) # Orange boxes for YOLO before mapping


    # 处理 YOLO 检测结果
    detection_polygons, detection_boxes, detection_labels = process_yolo_results(
        results, original_transform, TASK_ID, user_id, status, conn, type_id_to_class_id, inference_output_path
    )

    # 可视化推理结果 (YOLO boxes after mapping)
    if detection_boxes:
        draw_boxes_on_image(jpeg_path_extracted, detection_boxes, detection_labels, inference_output_path, color=(255, 0, 0)) # Red boxes for YOLO after mapping
    else:
        shutil.copy(jpeg_path_extracted, inference_output_path)
        print("无检测结果，保存原始图像作为推理结果可视化")

    # 删除数据库中旧的检测结果
    delete_existing_results_db(conn, TASK_ID)

    # 将新结果写入数据库
    insert_segmentation_results_db(conn, TASK_ID, detection_polygons, user_id, status)

    # 关闭数据库连接
    conn.close()
    print("任务完成!")

if __name__ == "__main__":
    main()