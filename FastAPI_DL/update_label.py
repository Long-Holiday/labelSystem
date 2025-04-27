import os
import sys
import psycopg2
import rasterio
import numpy as np
from shapely.geometry import Polygon
from psycopg2.extras import execute_values
from utils import connect_db, identify_holes_and_split  # 假设这是处理掩膜并生成多边形的工具函数

# 数据库连接信息（请替换为实际值）
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"
TABLE_NAME2 = "task"

# -------------------- 数据库操作函数 --------------------
# def connect_db():
#     """连接到PostgreSQL数据库"""
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

def fetch_map_server_from_db(conn, task_id):
    """从数据库中获取地图服务器路径"""
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
        query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {TABLE_NAME} WHERE task_id = %s ORDER BY id ASC"
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
    """将矢量化结果批量写入数据库"""
    if conn is None:
        return
    cursor = conn.cursor()
    values = [
        (', '.join(f"{x}, {y}" for x, y in polygon.exterior.coords), int(type_id), user_id, task_id, status)
        for type_id, polygons in segmentation_polygons.items()
        for polygon in polygons
    ]
    if values:
        execute_values(
            cursor,
            f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s",
            values
        )
        conn.commit()
        print(f"矢量化结果已成功写入数据库 task_id {task_id}，使用 user_id: {user_id}")
    else:
        print("没有生成任何多边形，未写入数据库。")
    cursor.close()

# -------------------- 掩膜生成函数 --------------------
def create_label_mask(labels_data, transform, img_height, img_width, background_class_index, type_id_to_class_index):
    """根据标签数据创建标签掩膜，一次性光栅化所有多边形"""
    mask = np.full((img_height, img_width), background_class_index, dtype=np.uint8)
    shapes = []
    for _, geom_str, type_id, *_ in labels_data:
        class_index = type_id_to_class_index.get(type_id)
        if class_index is None:
            continue
        try:
            coords_str_list = geom_str.split(',')
            coords_list = [(float(x.strip()), float(y.strip())) 
                           for x, y in zip(coords_str_list[::2], coords_str_list[1::2])]
            polygon = Polygon(coords_list)
            shapes.append((polygon, int(class_index)))
        except (ValueError, IndexError) as e:
            print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
            continue
    if shapes:
        mask = rasterio.features.rasterize(
            shapes=shapes,
            out_shape=(img_height, img_width),
            fill=background_class_index,
            transform=transform,
            all_touched=True,
            dtype=np.uint8
        )
    return mask

# -------------------- 主函数 --------------------
def update_label_function(argv):
    """主函数：处理任务并更新标签"""
    TASK_ID = int(argv[1])
    MAPFILE_PATH = argv[2]
    
    # 连接数据库
    # conn = db_conn
    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return
    
    # 获取地图服务器路径
    map_servers = fetch_map_server_from_db(conn, TASK_ID)
    if not map_servers:
        print(f"task_id {TASK_ID} 未找到地图服务器路径，请检查数据库。")
        conn.close()
        return
    map_name = map_servers[0][0]
    IMAGE_PATH = f"{MAPFILE_PATH}/{map_name}.tif"
    
    # 获取标签数据
    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
        conn.close()
        return
    
    user_id = labels_data[0][3]  # 从第一条记录获取 user_id
    status = labels_data[0][5]   # 从第一条记录获取 status
    
    # 读取影像元数据
    try:
        with rasterio.open(IMAGE_PATH) as src:
            transform = src.transform
            img_height, img_width = src.height, src.width
            crs = src.crs
            if crs != 'EPSG:3857':
                print(f"警告: 图像坐标系为 {crs}，不是 EPSG:3857，可能导致掩膜生成错误！")
    except rasterio.RasterioIOError as e:
        print(f"Error loading image: {e}")
        conn.close()
        return
    
    # 设置掩膜参数
    background_class_index = 0
    type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
    type_id_to_class_index = {type_id: idx + 1 for idx, type_id in enumerate(type_ids_from_db)}
    class_index_to_type_id = {idx: type_id for type_id, idx in type_id_to_class_index.items()}
    
    # 生成掩膜
    mask = create_label_mask(labels_data, transform, img_height, img_width, background_class_index, type_id_to_class_index)
    
    # 处理掩膜并生成多边形（假设 utils 模块提供此功能）
    segmentation_polygons = identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index)
    
    # 更新数据库
    delete_existing_results_db(conn, TASK_ID)
    insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)
    
    conn.close()
    print("任务完成!")

if __name__ == "__main__":
    update_label_function(sys.argv)

# import os
# import sys
# import psycopg2
# import rasterio
# import numpy as np
# from shapely.geometry import Polygon
# import rasterio.features
# from utils import identify_holes_and_split
# from numba import njit

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
#     """连接到PostgreSQL数据库"""
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

# def fetch_map_server_from_db(conn, task_id):
#     if conn is None:
#         return []
#     try:
#         cursor = conn.cursor()
#         query = f"SELECT map_server FROM {TABLE_NAME2} WHERE task_id = %s"
#         cursor.execute(query, (task_id,))
#         map_server = cursor.fetchall()
#         cursor.close()
#         return map_server
#     except psycopg2.Error as e:
#         print(f"Error fetching map_server from database: {e}")
#         return []

# def fetch_labels_from_db(conn, task_id):
#     """从数据库中获取指定 task_id 的标签数据，按 id 升序排序"""
#     if conn is None:
#         return []
#     try:
#         cursor = conn.cursor()
#         query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {TABLE_NAME} WHERE task_id = %s ORDER BY id ASC"
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

# def insert_segmentation_results_db(conn, task_id, segmentation_polygons, user_id, status):
#     """将矢量化结果写入数据库，使用原始坐标字符串格式"""
#     if conn is None:
#         return
#     cursor = conn.cursor()
#     insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s"

#     values_list = []
#     for type_id, polygons in segmentation_polygons.items():
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
#             print(f"矢量化结果已成功写入数据库 task_id {task_id}，使用 user_id: {user_id}")
#         except Exception as e:
#             conn.rollback()
#             print(f"写入数据库时出错: {e}")
#     else:
#         print("没有生成任何多边形，未写入数据库。")
#     cursor.close()

# # -------------------- 掩膜生成函数 --------------------
# # 将掩膜覆盖逻辑分离出来并使用 Numba 加速
# @njit
# def update_mask(mask, temp_mask, background_class_index):
#     height, width = mask.shape
#     for i in range(height):
#         for j in range(width):
#             if temp_mask[i, j] != background_class_index:
#                 mask[i, j] = temp_mask[i, j]
#     return mask

# def create_label_mask(labels_data, transform, img_height, img_width, background_class_index, type_id_to_class_index):
#     """根据标签数据创建标签掩膜，使用地理坐标，后面的多边形覆盖前面的"""
#     mask = np.full((img_height, img_width), background_class_index, dtype=np.uint8)
    
#     for _, geom_str, type_id, *_ in labels_data:
#         try:
#             # 解析坐标
#             coords_str_list = geom_str.split(',')
#             coords_list = []
#             for i in range(0, len(coords_str_list), 2):
#                 x = float(coords_str_list[i].strip())
#                 y = float(coords_str_list[i+1].strip())
#                 coords_list.append((x, y))
            
#             # 创建多边形
#             polygon = Polygon(coords_list)
#             class_index = type_id_to_class_index.get(type_id)
            
#             if class_index is not None:
#                 # 光栅化
#                 temp_mask = rasterio.features.rasterize(
#                     shapes=[(polygon, int(class_index))],
#                     out_shape=(img_height, img_width),
#                     fill=background_class_index,
#                     transform=transform,
#                     all_touched=True,
#                     dtype=np.uint8
#                 )
#                 # 使用 Numba 加速的掩膜更新
#                 mask = update_mask(mask, temp_mask, background_class_index)
#             else:
#                 print(f"警告: type_id {type_id} 未在映射中找到，已跳过。")
                
#         except (ValueError, IndexError) as e:
#             print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
#             continue
#         except ValueError as e:
#             print(f"光栅化多边形时出错: {e}")
#             continue
            
#     return mask
# # def create_label_mask(labels_data, transform, img_height, img_width, background_class_index, type_id_to_class_index):
# #     """根据标签数据创建标签掩膜，使用地理坐标，后面的多边形覆盖前面的"""
# #     mask = np.full((img_height, img_width), background_class_index, dtype=np.uint8)
# #     for _, geom_str, type_id, *_ in labels_data:
# #         try:
# #             coords_str_list = geom_str.split(',')
# #             coords_list = []
# #             for i in range(0, len(coords_str_list), 2):
# #                 x = float(coords_str_list[i].strip())
# #                 y = float(coords_str_list[i+1].strip())
# #                 coords_list.append((x, y))
# #             polygon = Polygon(coords_list)
# #             class_index = type_id_to_class_index.get(type_id)
# #             if class_index is not None:
# #                 temp_mask = rasterio.features.rasterize(
# #                     shapes=[(polygon, int(class_index))],
# #                     out_shape=(img_height, img_width),
# #                     fill=background_class_index,
# #                     transform=transform,
# #                     all_touched=True,
# #                     dtype=np.uint8
# #                 )
# #                 # 实现覆盖逻辑：非背景区域用新值替换
# #                 mask = np.where(temp_mask != background_class_index, temp_mask, mask)
# #             else:
# #                 print(f"警告: type_id {type_id} 未在映射中找到，已跳过。")
# #         except (ValueError, IndexError) as e:
# #             print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
# #             continue
# #         except ValueError as e:
# #             print(f"光栅化多边形时出错: {e}")
# #             continue
# #     return mask

# # -------------------- 掩膜转多边形函数 --------------------
# # def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
# #     current_exterior = exterior_coords[:]
    
# #     # 初始化 Rtree
# #     exterior_index = rtree.index.Index()
# #     for idx, (x, y) in enumerate(current_exterior):
# #         exterior_index.insert(idx, (x, y, x, y))
    
# #     for idx, interior_coords in enumerate(interior_coords_list):
# #         min_dist = float('inf')
# #         best_exterior_idx = 0
# #         best_interior_idx = 0
        
# #         for i, (ix, iy) in enumerate(interior_coords):
# #             nearest_idx = list(exterior_index.nearest((ix, iy, ix, iy), 1))[0]
# #             ex, ey = current_exterior[nearest_idx]
# #             dist = ((ix - ex) ** 2 + (iy - ey) ** 2) ** 0.5
# #             if dist < min_dist:
# #                 min_dist = dist
# #                 best_exterior_idx = nearest_idx
# #                 best_interior_idx = i
        
# #         # 构造新外环
# #         new_exterior = []
# #         new_exterior.extend(current_exterior[:best_exterior_idx + 1])
# #         reordered_interior = interior_coords[best_interior_idx:] + interior_coords[:best_interior_idx]
# #         new_exterior.extend(reordered_interior)
# #         new_exterior.append(reordered_interior[0])
# #         new_exterior.extend(current_exterior[best_exterior_idx:])
        
# #         # 更新 Rtree
# #         current_exterior = new_exterior
# #         exterior_index = rtree.index.Index()  # 重建（可选：动态插入）
# #         for j, (x, y) in enumerate(current_exterior):
# #             exterior_index.insert(j, (x, y, x, y))
    
# #     return current_exterior

# # def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index, min_area=30):
# #     """将掩膜转换为多边形，使用 connect_multiple_holes 处理孔洞"""
# #     polygons = {}
# #     for class_index in np.unique(mask):
# #         if class_index == background_class_index:
# #             continue
# #         type_id = class_index_to_type_id.get(class_index)
# #         if type_id is None:
# #             continue
# #         class_mask = (mask == class_index).astype(np.uint8)
# #         contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
# #         if hierarchy is None or len(contours) == 0:
# #             continue
# #         class_polygons = []
# #         i = 0
# #         while i < len(contours):
# #             if len(contours[i]) < 3 or cv2.contourArea(contours[i]) < min_area:
# #                 i += 1
# #                 continue
# #             if hierarchy[0][i][3] == -1:  # 外轮廓
# #                 exterior_coords = [transform * (point[0][0], point[0][1]) for point in contours[i]]
# #                 exterior_coords = [(x, y) for x, y in exterior_coords]
# #                 interior_contours = []
# #                 hole_idx = hierarchy[0][i][2]  # 第一个内轮廓索引
# #                 while hole_idx != -1:
# #                     if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
# #                         interior_coords = [transform * (point[0][0], point[0][1]) for point in contours[hole_idx]]
# #                         interior_coords = [(x, y) for x, y in interior_coords]
# #                         interior_contours.append(interior_coords)
# #                     hole_idx = hierarchy[0][hole_idx][0]  # 下一个内轮廓
# #                 if interior_contours:
# #                     final_coords = connect_multiple_holes(exterior_coords, interior_contours, max_distance=1000.0)
# #                 else:
# #                     final_coords = exterior_coords
# #                 try:
# #                     polygon = Polygon(final_coords)
# #                     class_polygons.append(polygon)
# #                 except Exception as e:
# #                     print(f"创建多边形时出错: {e}")
# #             i += 1
# #         if class_polygons:
# #             polygons[type_id] = class_polygons
# #     return polygons

# # -------------------- 主函数 --------------------
# def update_label_function(argv):
#     # 遥感影像路径和 task_id (请替换为你的实际信息)
#     TASK_ID = int(argv[1])
#     MAPFILE_PATH = argv[2]
#     # TASK_ID = 127
#     # IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"

#     # 连接数据库
#     conn = connect_db()
#     if conn is None:
#         print("无法连接到数据库，程序退出。")
#         return

#     # 获取地图服务器路径
#     map_servers = fetch_map_server_from_db(conn, TASK_ID)
#     if not map_servers:
#         print(f"task_id {TASK_ID} 未找到地图服务器路径，请检查数据库。")
#         conn.close()
#         return
#     # 假设 map_server 是单条记录，取第一个值
#     map_name = map_servers[0][0]  # fetchall 返回元组列表，提取第一个元组的第一个元素
#     IMAGE_PATH = f"{MAPFILE_PATH}/{map_name}.tif"  # 修正路径拼接，使用斜杠分隔

#     # 获取标签数据（按 id 升序）
#     labels_data = fetch_labels_from_db(conn, TASK_ID)
#     if not labels_data:
#         print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
#         conn.close()
#         return

#     # 提取 user_id 和 status（使用第一个记录的值）
#     user_id = labels_data[0][3]
#     status = labels_data[0][5]

#     # 加载遥感影像以获取 transform 和图像尺寸
#     try:
#         with rasterio.open(IMAGE_PATH) as src:
#             transform = src.transform
#             img_height, img_width = src.height, src.width
#             crs = src.crs
#             if crs != 'EPSG:3857':
#                 print(f"警告: 图像坐标系为 {crs}，不是 EPSG:3857，可能导致掩膜生成错误！")
#     except rasterio.RasterioIOError as e:
#         print(f"Error loading image: {e}")
#         conn.close()
#         return

#     # 设置背景类别索引
#     background_class_index = 0

#     # 创建类别映射
#     type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
#     type_id_to_class_index = {type_id: idx + 1 for idx, type_id in enumerate(type_ids_from_db)}  # 从 1 开始，0 为背景
#     class_index_to_type_id = {idx: type_id for type_id, idx in type_id_to_class_index.items()}

#     # 生成掩膜（按 id 顺序，后面的多边形覆盖前面的）
#     mask = create_label_mask(labels_data, transform, img_height, img_width, background_class_index, type_id_to_class_index)

#     # 矢量化掩膜，使用新的方法处理孔洞
#     segmentation_polygons = identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index)

#     # 删除数据库中旧的标注数据
#     delete_existing_results_db(conn, TASK_ID)

#     # 将新矢量化结果写入数据库
#     insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

#     # 关闭数据库连接
#     conn.close()
#     print("任务完成!")
