# # import os
# # import sys
# # import psycopg2
# # import rasterio
# # import numpy as np
# # from skimage.measure import regionprops, label
# # import torch
# # import torch.nn as nn
# # import torch.optim as optim
# # from torch.utils.data import Dataset, DataLoader
# # from shapely.geometry import Polygon
# # import rasterio.features
# # import matplotlib.pyplot as plt
# # import cv2
# # from skimage import morphology
# # from scipy.ndimage import generic_filter
# # import rtree.index

# # import os
# # import tempfile

# # import timm
# # import torch
# # from lightning.pytorch import Trainer

# # from torchgeo.datamodules import EuroSAT100DataModule
# # from torchgeo.models import DOFABase16_Weights
# # from torchgeo.trainers import SemanticSegmentationTask

# # # 数据库连接信息 (请替换为你的实际信息)
# # DB_HOST = "localhost"
# # DB_NAME = "label"
# # DB_USER = "postgres"
# # DB_PASSWORD = "123456"
# # DB_PORT = "5432"
# # TABLE_NAME = "mark"
# # TABLE_NAME2 = "task"

# # # -------------------- 数据库操作函数 --------------------
# # def connect_db():
# #     """连接到PostgreSQL数据库"""
# #     try:
# #         conn = psycopg2.connect(
# #             host=DB_HOST,
# #             database=DB_NAME,
# #             user=DB_USER,
# #             password=DB_PASSWORD,
# #             port=DB_PORT
# #         )
# #         return conn
# #     except psycopg2.Error as e:
# #         print(f"Error connecting to the database: {e}")
# #         return None

# # def fetch_map_server_from_db(conn, task_id):
# #     if conn is None:
# #         return []
# #     try:
# #         cursor = conn.cursor()
# #         query = f"SELECT map_server FROM {TABLE_NAME2} WHERE task_id = %s"
# #         cursor.execute(query, (task_id,))
# #         map_server = cursor.fetchall()
# #         cursor.close()
# #         return map_server
# #     except psycopg2.Error as e:
# #         print(f"Error fetching map_server from database: {e}")
# #         return []

# # def fetch_labels_from_db(conn, task_id):
# #     """从数据库中获取指定 task_id 的标签数据"""
# #     if conn is None:
# #         return []
# #     try:
# #         cursor = conn.cursor()
# #         query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {TABLE_NAME} WHERE task_id = %s"
# #         cursor.execute(query, (task_id,))
# #         labels_data = cursor.fetchall()
# #         cursor.close()
# #         return labels_data
# #     except psycopg2.Error as e:
# #         print(f"Error fetching labels from database: {e}")
# #         return []

# # def delete_existing_results_db(conn, task_id):
# #     """删除数据库中指定 task_id 的原有数据"""
# #     if conn is None:
# #         return
# #     cursor = conn.cursor()
# #     try:
# #         delete_query = f"DELETE FROM {TABLE_NAME} WHERE task_id = %s"
# #         cursor.execute(delete_query, (task_id,))
# #         conn.commit()
# #         print(f"已删除 task_id {task_id} 的原有数据。")
# #     except psycopg2.Error as e:
# #         print(f"Error deleting existing results from database: {e}")
# #         conn.rollback()
# #     finally:
# #         cursor.close()

# # def insert_segmentation_results_db(conn, task_id, segmentation_polygons, user_id, status):
# #     """将分割结果写入数据库，使用原始坐标字符串格式"""
# #     if conn is None:
# #         return
# #     cursor = conn.cursor()
# #     insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES %s"

# #     values_list = []
# #     for type_id, polygons in segmentation_polygons.items():
# #         for polygon in polygons:
# #             geom_str = ', '.join([f"{x}, {y}" for x, y in polygon.exterior.coords])
# #             values_list.append((cursor.mogrify("(%s, %s, %s, %s, %s)",
# #                                               (geom_str, int(type_id), user_id, task_id, status)).decode('utf-8')))

# #     if values_list:
# #         values_str = ','.join(values_list)
# #         full_insert_query = insert_query % values_str
# #         try:
# #             cursor.execute(full_insert_query)
# #             conn.commit()
# #             print(f"分割结果已成功写入数据库 task_id {task_id}，使用 user_id: {user_id}")
# #         except Exception as e:
# #             conn.rollback()
# #             print(f"写入数据库时出错: {e}")
# #     else:
# #         print("没有生成任何分割多边形，未写入数据库。")

# #     cursor.close()

# # # -------------------- 数据集定义 --------------------
# # class RemoteSensingSegmentationDataset(Dataset):
# #     def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index, background_class_index):
# #         self.image_path = image_path
# #         self.labels_data = labels_data
# #         self.num_classes = num_classes
# #         self.type_id_to_class_index = type_id_to_class_index
# #         self.background_class_index = background_class_index
# #         self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)
# #         self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])

# #     def _load_image(self, image_path):
# #         """加载遥感影像并进行预处理"""
# #         try:
# #             with rasterio.open(image_path) as src:
# #                 image = src.read()  # 读取所有波段 (C, H, W)
# #                 transform = src.transform
# #                 bounds = src.bounds
# #                 crs = src.crs
# #                 if crs != 'EPSG:3857':
# #                     print(f"警告: 图像坐标系为 {crs}，不是 EPSG:3857，可能导致掩膜生成错误！")
# #             image = image.astype(np.float32) / 255.0
# #             return image, transform, bounds, crs
# #         except rasterio.RasterioIOError as e:
# #             print(f"Error loading image: {e}")
# #             return None, None, None, None

# #     def _create_label_mask(self, labels_data, transform, img_height, img_width):
# #         """根据标签数据创建标签掩膜，使用地理坐标"""
# #         mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)
# #         shapes = []
# #         for _, geom_str, type_id, *_ in labels_data:
# #             try:
# #                 coords_str_list = geom_str.split(',')
# #                 coords_list = []
# #                 for i in range(0, len(coords_str_list), 2):
# #                     x = float(coords_str_list[i].strip())
# #                     y = float(coords_str_list[i+1].strip())
# #                     coords_list.append((x, y))
# #                 polygon = Polygon(coords_list)
# #                 class_index = self.type_id_to_class_index.get(type_id)
# #                 if class_index is not None:
# #                     shapes.append((polygon, int(class_index)))
# #                 else:
# #                     print(f"警告: type_id {type_id} 未在映射中找到，已跳过。")
# #             except (ValueError, IndexError) as e:
# #                 print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
# #                 continue
# #         if shapes:
# #             try:
# #                 mask = rasterio.features.rasterize(
# #                     shapes=shapes,
# #                     out_shape=(img_height, img_width),
# #                     fill=self.background_class_index,
# #                     transform=transform,
# #                     all_touched=True,
# #                     dtype=np.uint8
# #                 )
# #             except ValueError as e:
# #                 print(f"光栅化多边形时出错: {e}")
# #         return mask

# #     def __len__(self):
# #         return 1

# #     def __getitem__(self, idx):
# #         if self.image is None or self.label_mask is None:
# #             raise ValueError("Image or label mask is None. Check _load_image and _create_label_mask methods.")
# #         image_tensor = torch.from_numpy(self.image).float()
# #         mask_tensor = torch.from_numpy(self.label_mask).long()
# #         return image_tensor, mask_tensor
    
# # # -------------------- 掩膜转多边形函数 --------------------


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
# #             if hierarchy[0][i][3] == -1:
# #                 exterior_coords = [transform * (point[0][0], point[0][1]) for point in contours[i]]
# #                 exterior_coords = [(x, y) for x, y in exterior_coords]
# #                 interior_contours = []
# #                 hole_idx = hierarchy[0][i][2]
# #                 while hole_idx != -1:
# #                     if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
# #                         interior_coords = [transform * (point[0][0], point[0][1]) for point in contours[hole_idx]]
# #                         interior_coords = [(x, y) for x, y in interior_coords]
# #                         interior_contours.append(interior_coords)
# #                     hole_idx = hierarchy[0][hole_idx][0]
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


# # # -------------------- 主函数 --------------------
# # def main():
# #     # 遥感影像路径和 task_id (请替换为你的实际信息)
# #     TASK_ID = 133
# #     IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"

# #     # 训练参数 (可以根据需要调整)
# #     batch_size = 10
# #     num_workers = 2
# #     max_epochs = 10
# #     fast_dev_run = False

# #     # 检查GPU是否可用
# #     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# #     print(f"Using device: {device}")

# #     # 连接数据库
# #     conn = connect_db()
# #     if conn is None:
# #         print("无法连接到数据库，程序退出。")
# #         return

# #     # 获取原始标签数据以提取 user_id 和 status
# #     original_row_data = fetch_labels_from_db(conn, TASK_ID)
# #     if not original_row_data:
# #         print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
# #         conn.close()
# #         return

# #     # 检查并提取唯一的 user_id 和 status
# #     user_ids = set(row[3] for row in original_row_data)
# #     if len(user_ids) > 1:
# #         print(f"警告: task_id {TASK_ID} 包含多个 user_id: {user_ids}，使用第一个")
# #     user_id = original_row_data[0][3]
# #     status = original_row_data[0][5]

# #     # 用于训练的标签数据
# #     labels_data = original_row_data

# #     # 动态确定分类数量和创建类别映射
# #     type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))
# #     num_classes = len(type_ids_from_db) + 1
# #     type_id_to_class_index = {type_id: index for index, type_id in enumerate(type_ids_from_db)}
# #     background_class_index = num_classes - 1
# #     class_index_to_type_id = {index: type_id for type_id, index in type_id_to_class_index.items()}

# #     # 创建数据集和数据加载器
# #     dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, background_class_index)
# #     dataloader = DataLoader(dataset, batch_size=max_epochs)


# #     # 读取遥感影像波段数
# #     with rasterio.open(IMAGE_PATH) as src:
# #         n_channels = src.count  # 获取波段数

# #     # 初始化模型，使用动态确定的 n_channels
# #     weights = DOFABase16_Weights.DOFA_MAE
# #     # model = LightUNet(in_channels=n_channels, num_classes=num_classes).to(device) # Changed to LightUNet
# #     loss_fn = nn.CrossEntropyLoss()
# #     optimizer = optim.SGD(model.parameters(), lr=1e-2)
# #     model = model.to(device)

# #     # 训练模型
# #     task = SemanticSegmentationTask(
# #     model='resnet18',
# #     loss='ce',
# #     weights=weights,
# #     in_channels=n_channels,
# #     num_classes=num_classes,
# #     lr=0.001,
# #     patience=5,
# #     )

# #     accelerator = 'gpu' if torch.cuda.is_available() else 'cpu'
# #     default_root_dir = os.path.join(tempfile.gettempdir(), 'experiments')

# #     trainer = Trainer(
# #     accelerator=accelerator,
# #     default_root_dir=default_root_dir,
# #     fast_dev_run=fast_dev_run,
# #     log_every_n_steps=1,
# #     min_epochs=1,
# #     max_epochs=max_epochs,
# #     )

# #     trainer.fit(model=task, datamodule=dataloader)


# #     # 加载原始图像用于分割
# #     original_image_np, original_transform, _, _ = dataset._load_image(IMAGE_PATH)
# #     if original_image_np is None:
# #         print("Failed to load original image for segmentation. Exiting.")
# #         conn.close()
# #         return

# #     # 分割预测
# #     original_image_tensor = torch.from_numpy(original_image_np).float()
# #     # predicted_mask_np = segment_image(model, original_image_tensor, device, num_classes)

# #     # 转换为多边形并处理多个内环
# #     segmentation_polygons = identify_holes_and_split(
# #         predicted_mask_np, original_transform, class_index_to_type_id, background_class_index, min_area=1
# #     )


# #     # 删除数据库中旧的分割结果
# #     delete_existing_results_db(conn, TASK_ID)

# #     # 将新分割结果写入数据库，使用原始的 user_id 和 status
# #     insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

# #     # 关闭数据库连接
# #     conn.close()
# #     print("任务完成!")

# # if __name__ == "__main__":
# #     main()

# # --- START OF FILE torchgeo_test.py ---

# import math
# import os
# import tempfile
# import psycopg2
# import rasterio
# import numpy as np
# import torch
# import torch.nn as nn
# from torch.utils.data import Dataset, DataLoader
# from shapely.geometry import Polygon
# import rasterio.features
# import cv2
# import torch.nn.functional as F
# # from skimage import morphology # Not used in the final version, can be removed if hole connection doesn't need it
# # from scipy.ndimage import generic_filter # Not used
# import rtree.index # Required for identify_holes_and_split

# # PyTorch Lightning and TorchGeo Imports
# from lightning.pytorch import Trainer
# # Removed: from torchgeo.datamodules import EuroSAT100DataModule (Not suitable for this custom task)
# from torchgeo.models import DOFABase16_Weights # Keep selected weights
# # Import the specific model if needed for type hinting, but Task handles creation
# # from torchgeo.models import DOFABasePatch16_224 # Example model compatible with weights
# from torchgeo.trainers import SemanticSegmentationTask,ClassificationTask

# # --- Database Configuration ---
# DB_HOST = "localhost"
# DB_NAME = "label"
# DB_USER = "postgres"
# DB_PASSWORD = "123456"
# DB_PORT = "5432"
# TABLE_NAME = "mark"
# TABLE_NAME2 = "task"

# # -------------------- Database Operation Functions --------------------
# def connect_db():
#     """Connects to the PostgreSQL database."""
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

# # --- Other DB functions (fetch_map_server_from_db, fetch_labels_from_db, delete_existing_results_db, insert_segmentation_results_db) remain the same ---
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
#     """Fetches label data for a specific task_id from the database."""
#     if conn is None:
#         return []
#     try:
#         cursor = conn.cursor()
#         # Ensure the geom column is selected correctly based on your DB schema
#         query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {TABLE_NAME} WHERE task_id = %s"
#         cursor.execute(query, (task_id,))
#         labels_data = cursor.fetchall()
#         cursor.close()
#         return labels_data
#     except psycopg2.Error as e:
#         print(f"Error fetching labels from database: {e}")
#         return []

# def delete_existing_results_db(conn, task_id):
#     """Deletes existing data for a specific task_id from the database."""
#     if conn is None:
#         return
#     cursor = conn.cursor()
#     try:
#         # Use a placeholder for task_id to prevent SQL injection
#         delete_query = f"DELETE FROM {TABLE_NAME} WHERE task_id = %s"
#         cursor.execute(delete_query, (task_id,))
#         conn.commit()
#         print(f"Deleted existing data for task_id {task_id}.")
#     except psycopg2.Error as e:
#         print(f"Error deleting existing results from database: {e}")
#         conn.rollback()
#     finally:
#         cursor.close()

# def insert_segmentation_results_db(conn, task_id, segmentation_polygons, user_id, status):
#     """Inserts segmentation results (polygons) into the database."""
#     if conn is None or not segmentation_polygons:
#         print("No connection or no polygons to insert.")
#         return

#     cursor = conn.cursor()
#     # Use mogrify correctly for parameter substitution in VALUES
#     insert_query_template = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES (%s, %s, %s, %s, %s)"
#     values_to_insert = []

#     for type_id, polygons in segmentation_polygons.items():
#         for polygon in polygons:
#             # Ensure polygon is valid and has coordinates
#             if polygon and polygon.exterior and polygon.exterior.coords:
#                 # Format coordinates as 'x1, y1, x2, y2, ...' string
#                 geom_str = ', '.join([f"{x}, {y}" for x, y in polygon.exterior.coords])
#                 values_to_insert.append((geom_str, int(type_id), user_id, task_id, status))
#             else:
#                 print(f"Warning: Skipping invalid or empty polygon for type_id {type_id}")


#     if values_to_insert:
#         try:
#             # Use execute_batch for efficiency if supported, otherwise loop execute
#             # psycopg2's execute_values is often preferred if available via extras
#             # Simple loop execute for compatibility:
#             for values in values_to_insert:
#                  cursor.execute(insert_query_template, values)

#             # Alternative using mogrify (less safe if not careful, original approach was flawed)
#             # values_list_mogrified = []
#             # for values in values_to_insert:
#             #     values_list_mogrified.append(cursor.mogrify("(%s, %s, %s, %s, %s)", values).decode('utf-8'))
#             # if values_list_mogrified:
#             #     values_str = ','.join(values_list_mogrified)
#             #     full_insert_query = f"INSERT INTO {TABLE_NAME} (geom, type_id, user_id, task_id, status) VALUES {values_str}"
#             #     cursor.execute(full_insert_query)

#             conn.commit()
#             print(f"Inserted {len(values_to_insert)} segmentation results for task_id {task_id} with user_id: {user_id}")
#         except Exception as e:
#             conn.rollback()
#             print(f"Error inserting into database: {e}")
#     else:
#         print("No valid segmentation polygons generated, nothing inserted into the database.")

#     cursor.close()


# # -------------------- Dataset Definition --------------------
# class RemoteSensingSegmentationDataset(Dataset):
#     """Custom Dataset for loading a single remote sensing image and its labels from DB."""
#     def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index, background_class_index):
#         self.image_path = image_path
#         self.labels_data = labels_data
#         self.num_classes = num_classes
#         self.type_id_to_class_index = type_id_to_class_index
#         self.background_class_index = background_class_index
#         self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)
#         if self.image is None:
#              raise FileNotFoundError(f"Failed to load image: {image_path}")
#         self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])

#     def _load_image(self, image_path):
#         """Loads the remote sensing image and basic metadata."""
#         try:
#             with rasterio.open(image_path) as src:
#                 image = src.read()  # Reads all bands (C, H, W)
#                 transform = src.transform
#                 bounds = src.bounds
#                 crs = src.crs
#                 print(f"Image loaded: shape={image.shape}, CRS={crs}, Transform={transform}")
#                 # Basic check for common projection (optional but good practice)
#                 # if crs and crs.to_epsg() != 3857:
#                 #    print(f"Warning: Image CRS is {crs}, not EPSG:3857. Ensure label coordinates match.")
#             # Normalize - check if model weights require different normalization
#             image = image.astype(np.float32) / 255.0
#             return image, transform, bounds, crs
#         except rasterio.RasterioIOError as e:
#             print(f"Error loading image {image_path}: {e}")
#             return None, None, None, None
#         except Exception as e:
#             print(f"An unexpected error occurred loading image {image_path}: {e}")
#             return None, None, None, None


#     def _create_label_mask(self, labels_data, transform, img_height, img_width):
#         """Creates a label mask from geometry data fetched from the database."""
#         mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)
#         shapes = []
#         if not labels_data:
#             print("Warning: No labels data provided to create mask.")
#             return mask # Return background mask

#         for label_row in labels_data:
#             # Adjust indices based on fetch_labels_from_db output order
#             geom_str = label_row[1] # Assuming geom is the second column
#             type_id = label_row[2]  # Assuming type_id is the third column

#             if not isinstance(geom_str, str):
#                 print(f"Warning: Invalid geometry data type for label row {label_row[0]}, skipping.")
#                 continue

#             try:
#                 # Parse coordinate string 'x1, y1, x2, y2, ...'
#                 coords_str_list = geom_str.split(',')
#                 if len(coords_str_list) < 6: # Need at least 3 points for a polygon
#                      print(f"Warning: Not enough coordinates for polygon in row {label_row[0]}, skipping.")
#                      continue
#                 coords_list = []
#                 for i in range(0, len(coords_str_list), 2):
#                     x = float(coords_str_list[i].strip())
#                     y = float(coords_str_list[i+1].strip())
#                     coords_list.append((x, y))

#                 # Ensure the polygon is closed (first and last points are the same)
#                 if coords_list[0] != coords_list[-1]:
#                     coords_list.append(coords_list[0])

#                 polygon = Polygon(coords_list)
#                 class_index = self.type_id_to_class_index.get(type_id)

#                 if class_index is not None:
#                     # Rasterize expects list of (geometry, value) tuples
#                     shapes.append((polygon, int(class_index)))
#                 else:
#                     print(f"Warning: type_id {type_id} not found in mapping, skipping label row {label_row[0]}.")
#             except (ValueError, IndexError, TypeError) as e:
#                 print(f"Error processing geometry string for label row {label_row[0]}: {e}. Geom string: '{geom_str[:50]}...'")
#                 continue
#             except Exception as e:
#                  print(f"Unexpected error processing geometry for label row {label_row[0]}: {e}")
#                  continue

#         if shapes:
#             try:
#                 # Rasterize features onto the mask
#                 mask = rasterio.features.rasterize(
#                     shapes=shapes,
#                     out_shape=(img_height, img_width),
#                     fill=self.background_class_index, # Fill value for background
#                     transform=transform,
#                     all_touched=True, # Consider pixels touched by polygon boundaries
#                     dtype=np.uint8
#                 )
#                 print(f"Successfully rasterized {len(shapes)} shapes onto the mask.")
#             except ValueError as e:
#                 print(f"Error during rasterization: {e}")
#             except Exception as e:
#                  print(f"Unexpected error during rasterization: {e}")
#         else:
#             print("No valid shapes found to rasterize.")

#         return mask

#     def __len__(self):
#         # This dataset represents a single image
#         return 1

#     # Inside class RemoteSensingSegmentationDataset:

#     def __getitem__(self, idx):
#         if idx != 0:
#             raise IndexError("This dataset only contains a single item.")
#         if self.image is None or self.label_mask is None:
#             raise ValueError("Image or label mask not loaded properly.")

#         image_tensor = torch.from_numpy(self.image).float()
#         mask_tensor = torch.from_numpy(self.label_mask).long()

#         # --- 修改填充逻辑，使用 32 作为除数 ---
#         _, height, width = image_tensor.shape
#         divisor = 32 # <--- 修改这里为 32
#         target_height = math.ceil(height / divisor) * divisor
#         target_width = math.ceil(width / divisor) * divisor

#         # 如果尺寸已经符合要求，则不需要填充
#         if height != target_height or width != target_width:
#             pad_height = target_height - height
#             pad_width = target_width - width

#             # 计算需要添加到四周的 padding 量 (尽量均匀分布)
#             pad_top = pad_height // 2
#             pad_bottom = pad_height - pad_top
#             pad_left = pad_width // 2
#             pad_right = pad_width - pad_left

#             padding = (pad_left, pad_right, pad_top, pad_bottom)

#             # 填充图像
#             image_tensor = F.pad(image_tensor, padding, mode='constant', value=0)

#             # 填充掩码
#             mask_tensor = mask_tensor.unsqueeze(0)
#             mask_tensor = F.pad(mask_tensor, padding, mode='constant', value=self.background_class_index)
#             mask_tensor = mask_tensor.squeeze(0)

#             # print(f"Padded image shape to {divisor}-divisible: {image_tensor.shape}")
#             # print(f"Padded mask shape to {divisor}-divisible: {mask_tensor.shape}")
#         # --- 填充逻辑结束 ---

#         # 返回包含填充后张量的字典
#         return {"image": image_tensor, "mask": mask_tensor}

# # -------------------- Mask to Polygon Functions --------------------
# # --- connect_multiple_holes and identify_holes_and_split functions remain the same ---
# # Ensure rtree, opencv-python, shapely are installed: pip install rtree opencv-python shapely

# def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
#     """Connects multiple interior holes to an exterior boundary using R-tree for efficiency."""
#     if not interior_coords_list:
#         return exterior_coords

#     current_exterior = exterior_coords[:]
#     remaining_interiors = interior_coords_list[:]

#     # Build R-tree index for the current exterior boundary
#     exterior_index = rtree.index.Index()
#     for idx, point in enumerate(current_exterior):
#         exterior_index.insert(idx, (*point, *point)) # (minx, miny, maxx, maxy)

#     final_coords = list(current_exterior) # Start with the exterior

#     while remaining_interiors:
#         best_exterior_pt_idx = -1
#         best_interior_pt_idx = -1
#         best_interior_hole_idx = -1
#         min_dist_sq = float('inf')

#         # Find the closest point pair between any remaining interior and the current exterior
#         for hole_idx, interior_coords in enumerate(remaining_interiors):
#             for interior_pt_idx, (ix, iy) in enumerate(interior_coords):
#                 # Find nearest point on exterior using R-tree
#                 nearest_exterior_indices = list(exterior_index.nearest((ix, iy, ix, iy), 1))
#                 if not nearest_exterior_indices: continue
#                 nearest_ext_idx = nearest_exterior_indices[0]
#                 ex, ey = final_coords[nearest_ext_idx] # Get coords from potentially updated final_coords

#                 dist_sq = (ix - ex)**2 + (iy - ey)**2
#                 if dist_sq < min_dist_sq:
#                     min_dist_sq = dist_sq
#                     best_exterior_pt_idx = nearest_ext_idx
#                     best_interior_pt_idx = interior_pt_idx
#                     best_interior_hole_idx = hole_idx

#         if best_exterior_pt_idx == -1:
#             print("Warning: Could not find connection point for remaining holes.")
#             break # Cannot connect further

#         # Get the chosen interior hole and reorder it
#         chosen_interior = remaining_interiors.pop(best_interior_hole_idx)
#         reordered_interior = chosen_interior[best_interior_pt_idx:] + chosen_interior[:best_interior_pt_idx]
#         # Ensure closing point matches start point for the cut
#         connection_point_exterior = final_coords[best_exterior_pt_idx]

#         # Construct the new exterior path
#         new_final_coords = (
#             final_coords[:best_exterior_pt_idx+1] + # Part before cut
#             reordered_interior +                    # Insert reordered hole
#             [reordered_interior[0]] +               # Close the hole path back to its start
#             [connection_point_exterior] +           # Bridge back to exterior point
#             final_coords[best_exterior_pt_idx+1:]   # Part after cut
#         )

#         # Update final_coords and rebuild R-tree for the next iteration
#         final_coords = new_final_coords
#         exterior_index = rtree.index.Index()
#         for idx, point in enumerate(final_coords):
#             exterior_index.insert(idx, (*point, *point))


#     return final_coords


# def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index, min_area=30):
#     """Converts a segmentation mask to polygons, handling holes using connect_multiple_holes."""
#     segmentation_polygons = {}
#     unique_classes = np.unique(mask)

#     for class_index in unique_classes:
#         if class_index == background_class_index:
#             continue

#         type_id = class_index_to_type_id.get(class_index)
#         if type_id is None:
#             print(f"Warning: No type_id mapping for class index {class_index}, skipping.")
#             continue

#         # Create a binary mask for the current class
#         class_mask = (mask == class_index).astype(np.uint8)

#         # Find contours - RETR_CCOMP finds external contours and holes
#         contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

#         if hierarchy is None or len(contours) == 0:
#             continue

#         class_polygons_list = []
#         # Hierarchy: [Next, Previous, First_Child, Parent]
#         # Iterate through top-level contours (potential exteriors)
#         i = 0
#         while i >= 0: # Iterate through contours at the current level
#             contour = contours[i]
#             # Check if it's an exterior contour (hierarchy[0][i][3] == -1)
#             if hierarchy[0][i][3] == -1:
#                 # Basic check for minimum points and area
#                 if len(contour) >= 3 and cv2.contourArea(contour) >= min_area:
#                     # Convert pixel coords to geo coords
#                     exterior_geo_coords = [tuple(transform * (p[0][0], p[0][1])) for p in contour]
#                     # Ensure closure
#                     if exterior_geo_coords[0] != exterior_geo_coords[-1]:
#                          exterior_geo_coords.append(exterior_geo_coords[0])


#                     interior_contours_geo = []
#                     # Find immediate children (holes)
#                     hole_idx = hierarchy[0][i][2] # First child
#                     while hole_idx != -1:
#                         hole_contour = contours[hole_idx]
#                         if len(hole_contour) >= 3 and cv2.contourArea(hole_contour) >= min_area: # Optional: min area for holes too
#                             interior_geo_coords = [tuple(transform * (p[0][0], p[0][1])) for p in hole_contour]
#                              # Ensure closure
#                             if interior_geo_coords[0] != interior_geo_coords[-1]:
#                                 interior_geo_coords.append(interior_geo_coords[0])
#                             interior_contours_geo.append(interior_geo_coords)
#                         hole_idx = hierarchy[0][hole_idx][0] # Next sibling hole

#                     # Connect holes if they exist
#                     if interior_contours_geo:
#                         # print(f"Connecting {len(interior_contours_geo)} holes for contour {i}")
#                         final_boundary_coords = connect_multiple_holes(exterior_geo_coords, interior_contours_geo)
#                     else:
#                         final_boundary_coords = exterior_geo_coords

#                     try:
#                         # Create Shapely Polygon
#                         final_polygon = Polygon(final_boundary_coords)
#                         # Optional: Check validity and simplify if needed
#                         if not final_polygon.is_valid:
#                             print(f"Warning: Generated polygon for class {type_id} is invalid, attempting buffer(0)")
#                             final_polygon = final_polygon.buffer(0)
#                         if final_polygon.is_valid and not final_polygon.is_empty:
#                              class_polygons_list.append(final_polygon)
#                         else:
#                             print(f"Warning: Skipping empty or invalid polygon after buffer for class {type_id}")
#                     except Exception as e:
#                         print(f"Error creating polygon for class {type_id}: {e}")
#                         # print("Coords:", final_boundary_coords[:5]) # Debug print first few coords

#             # Move to the next contour at the same level
#             i = hierarchy[0][i][0] # Next contour index

#         if class_polygons_list:
#             segmentation_polygons[type_id] = class_polygons_list
#             print(f"Generated {len(class_polygons_list)} polygons for type_id {type_id}")

#     return segmentation_polygons


# # -------------------- Main Function --------------------
# def main():
#     # Configuration
#     TASK_ID = 133 # Example Task ID
#     # Ensure this path is correct and accessible
#     IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"
#     if not os.path.exists(IMAGE_PATH):
#         print(f"Error: Image file not found at {IMAGE_PATH}")
#         return

#     # Training parameters
#     batch_size = 1 # Process the single large image
#     num_workers = 2 # For DataLoader
#     max_epochs = 10 # Number of fine-tuning epochs
#     learning_rate = 1e-3
#     patience = 5 # For LR scheduler in SemanticSegmentationTask
#     fast_dev_run = False # Set to True for a quick debug run (1 batch train/val)

#     # Setup device
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"Using device: {device}")

#     # Connect to database
#     conn = connect_db()
#     if conn is None:
#         print("Database connection failed. Exiting.")
#         return

#     # Fetch original label data to get metadata (user_id, status) and for training mask
#     original_row_data = fetch_labels_from_db(conn, TASK_ID)
#     if not original_row_data:
#         print(f"No label data found for task_id {TASK_ID}. Exiting.")
#         conn.close()
#         return

#     # Extract user_id and status (assuming constant for the task)
#     user_id = original_row_data[0][3]
#     status = original_row_data[0][5]
#     print(f"Using user_id: {user_id}, status: {status} for task {TASK_ID}")

#     # Determine classes and mappings dynamically from fetched labels
#     type_ids_from_db = sorted(list(set(row[2] for row in original_row_data)))
#     if not type_ids_from_db:
#          print(f"Warning: No type_ids found in the fetched labels for task {TASK_ID}.")
#          # Decide how to handle this - exit or proceed with background only?
#          # For now, let's assume at least one type_id exists or background is sufficient
#     num_classes = len(type_ids_from_db) + 1 # Add 1 for background
#     # Map database type_id -> zero-based class index for model
#     type_id_to_class_index = {type_id: index for index, type_id in enumerate(type_ids_from_db)}
#     background_class_index = num_classes - 1
#     # Map model's class index -> database type_id for saving results
#     class_index_to_type_id = {index: type_id for type_id, index in type_id_to_class_index.items()}
#     print(f"Detected {len(type_ids_from_db)} foreground classes. Total classes (incl. background): {num_classes}")
#     print(f"Type ID to Class Index mapping: {type_id_to_class_index}")
#     print(f"Background class index: {background_class_index}")


#     # Create Dataset
#     try:
#         dataset = RemoteSensingSegmentationDataset(
#             IMAGE_PATH,
#             original_row_data, # Use fetched data for mask creation
#             num_classes,
#             type_id_to_class_index,
#             background_class_index
#         )
#     except Exception as e:
#         print(f"Error creating dataset: {e}")
#         conn.close()
#         return

#     # Create DataLoader
#     # Since len(dataset) is 1, this loader yields the single image/mask pair
#     dataloader = DataLoader(dataset, batch_size=batch_size, num_workers=num_workers, shuffle=False) # Shuffle=False for single item

#     # Get number of input channels from the loaded image
#     n_channels = dataset.image.shape[0]
#     print(f"Image has {n_channels} channels.")

#     # --- Model Training/Fine-tuning ---
#     # Define the task using TorchGeo trainer
#     # Using DOFA model as weights were specified
#     task = SemanticSegmentationTask(
#         model='unet', # Model compatible with DOFA weights
#         backbone="resnet50",
#         # weights=weights,               # Load pre-trained weights
#         in_channels=n_channels,        # Set dynamically from image
#         num_classes=num_classes,       # Set dynamically from labels
#         loss='ce',                     # CrossEntropyLoss suitable for multi-class segmentation
#         lr=learning_rate,
#         patience=patience,
#         # freeze_backbone=True, # Optional: Freeze backbone for fine-tuning only the head
#         # freeze_decoder=True, # Optional: Freeze decoder too
#     )

#     # Configure PyTorch Lightning Trainer
#     accelerator = 'gpu' if torch.cuda.is_available() else 'cpu'
#     default_root_dir = os.path.join(tempfile.gettempdir(), 'torchgeo_experiments')
#     os.makedirs(default_root_dir, exist_ok=True)

#     trainer = Trainer(
#         accelerator=accelerator,
#         devices=1 if accelerator == 'gpu' else None, # Specify number of GPUs if using GPU
#         default_root_dir=default_root_dir,
#         fast_dev_run=fast_dev_run,      # Set to True for quick debug run
#         log_every_n_steps=1,
#         min_epochs=1,                   # Ensure at least 1 epoch runs
#         max_epochs=max_epochs,
#         # Add callbacks like ModelCheckpoint if needed
#     )

#     print("Starting model fine-tuning...")
#     # Train the model (fine-tune on the single image/mask)
#     # Pass the dataloader directly. Using the same for validation is not true validation
#     # but necessary if trainer expects val_dataloader and we only have one item.
#     # Alternatively, disable validation loop if possible/desired.
#     try:
#         trainer.fit(model=task, train_dataloaders=dataloader, val_dataloaders=dataloader)
#         print("Fine-tuning finished.")
#     except Exception as e:
#         print(f"Error during training: {e}")
#         conn.close()
#         return


#     # --- Prediction ---
#     print("Starting prediction on the image...")
#     # Use trainer.predict to get the segmentation mask for the input image
#     # Ensure the model is in eval mode (trainer.predict handles this)
#     try:
#         predictions = trainer.predict(model=task, dataloaders=dataloader)
#     except Exception as e:
#         print(f"Error during prediction: {e}")
#         conn.close()
#         return

#     # Process prediction output
#     predicted_mask_np = None
#     if predictions and isinstance(predictions, list) and len(predictions) > 0:
#         # trainer.predict returns a list of outputs per batch.
#         # Our dataloader has 1 batch. The output structure depends on predict_step.
#         # SemanticSegmentationTask likely returns {'image': ..., 'mask': ..., 'prediction': ...}
#         # Let's assume the prediction tensor is under the key 'prediction'
#         prediction_batch = predictions[0]
#         if isinstance(prediction_batch, dict) and 'prediction' in prediction_batch:
#             predicted_mask_tensor = prediction_batch['prediction'] # Shape [B, H, W] or [B, C, H, W]
#             # If logits (C > 1), get argmax. If labels (C=1 or no C dim), use directly.
#             if predicted_mask_tensor.ndim == 4 and predicted_mask_tensor.shape[1] > 1:
#                 predicted_mask_tensor = torch.argmax(predicted_mask_tensor, dim=1) # [B, H, W]

#             # Remove batch dim (B=1), move to CPU, convert to numpy uint8
#             predicted_mask_np = predicted_mask_tensor.squeeze(0).cpu().numpy().astype(np.uint8)
#             print(f"Prediction successful. Mask shape: {predicted_mask_np.shape}")
#         else:
#             print("Error: Prediction output format not as expected (expected dict with 'prediction' key).")
#             print(f"Prediction output type: {type(prediction_batch)}, content: {prediction_batch}")

#     if predicted_mask_np is None:
#         print("Failed to generate prediction mask. Exiting.")
#         conn.close()
#         return
    
#     if predicted_mask_np is not None:
#     # --- 确认裁剪逻辑 ---
#     # 确保 dataset.image 仍然是原始未填充的图像，以便获取 original_height/width
#     # 如果 dataset.image 被修改了，你需要从其他地方获取原始尺寸
#         try:
#             original_height = dataset.image.shape[1] # 获取原始高度
#             original_width = dataset.image.shape[2]  # 获取原始宽度
#         except AttributeError:
#             # 如果 dataset.image 可能不存在或不是 numpy 数组了
#             # 你需要提前保存原始尺寸，例如在 __init__ 或 _load_image 中
#             print("Error: Cannot get original image dimensions from dataset.image.")
#             # 这里需要一个备用方案来获取 original_height, original_width
#             # 例如: original_height, original_width = 741, 921 (如果确定)
#             # 或者从 self.original_shape 等保存的属性中获取
#             # return # 或者引发错误

#         padded_height = predicted_mask_np.shape[0] # 获取填充后高度 (例如 768)
#         padded_width = predicted_mask_np.shape[1]  # 获取填充后宽度 (例如 928)

#         if padded_height > original_height or padded_width > original_width:
#             pad_height_total = padded_height - original_height
#             pad_width_total = padded_width - original_width
#             # 重新计算 pad_top 和 pad_left，基于当前的填充后尺寸和原始尺寸
#             pad_top = pad_height_total // 2
#             pad_left = pad_width_total // 2

#             # 裁剪回原始尺寸
#             predicted_mask_np_cropped = predicted_mask_np[pad_top:pad_top + original_height, pad_left:pad_left + original_width]
#             print(f"Cropped prediction mask back to original shape: {predicted_mask_np_cropped.shape}")
#         else:
#             # 如果没有填充，直接使用
#             predicted_mask_np_cropped = predicted_mask_np
#         # --- 裁剪逻辑结束 ---

#     # --- Post-processing: Mask to Polygons ---
#     print("Converting prediction mask to polygons...")
#     # Use the transform from the loaded dataset for coordinate conversion
#     original_transform = dataset.transform
#     segmentation_polygons = identify_holes_and_split(
#         predicted_mask_np,
#         original_transform,
#         class_index_to_type_id,
#         background_class_index,
#         min_area=1 # Adjust minimum polygon area as needed
#     )
#     print(f"Polygon conversion finished. Found polygons for {len(segmentation_polygons)} classes.")

#     # --- Database Update ---
#     # Delete old results for this task ID
#     delete_existing_results_db(conn, TASK_ID)

#     # Insert new results
#     insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

#     # Close database connection
#     conn.close()
#     print("Task completed successfully!")

# if __name__ == "__main__":
#     # Add checks for required libraries
#     try:
#         import rtree
#         import cv2
#         import shapely
#         import lightning # or lightning.pytorch
#         import torchgeo
#         import psycopg2
#         import rasterio
#     except ImportError as e:
#         print(f"Missing required library: {e.name}. Please install it.")
#         print("Try: pip install torchgeo rtree opencv-python shapely 'lightning>=2.0' psycopg2-binary rasterio")
#         exit(1)

#     main()

# # --- END OF FILE torchgeo_test.py ---

import math
import os
import tempfile
import psycopg2
import rasterio
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from shapely.geometry import Polygon
import rasterio.features
import cv2
import rtree.index
from lightning.pytorch import Trainer
from torchgeo.trainers import SemanticSegmentationTask

# --- 数据库配置 ---
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
        print(f"从数据库获取标签数据错误: {e}")
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
    except psycopg2.Error as e:
        print(f"删除数据库现有结果错误: {e}")
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
            print(f"写入数据库时出错: {e}")
    else:
        print("没有生成任何分割多边形，未写入数据库。")

    cursor.close()


# -------------------- 数据集定义 --------------------
class RemoteSensingSegmentationDataset(Dataset):
    """自定义遥感分割数据集"""
    def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index, background_class_index):
        self.image_path = image_path
        self.labels_data = labels_data
        self.num_classes = num_classes
        self.type_id_to_class_index = type_id_to_class_index
        self.background_class_index = background_class_index
        self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)
        if self.image is None:
            raise FileNotFoundError(f"无法加载图像: {image_path}")
        self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])

    def _load_image(self, image_path):
        """加载遥感影像"""
        try:
            with rasterio.open(image_path) as src:
                image = src.read()
                transform = src.transform
                bounds = src.bounds
                crs = src.crs
            image = image.astype(np.float32) / 255.0
            return image, transform, bounds, crs
        except rasterio.RasterioIOError as e:
            print(f"加载图像错误 {image_path}: {e}")
            return None, None, None, None

    def _create_label_mask(self, labels_data, transform, img_height, img_width):
        """根据标签数据创建掩膜"""
        mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)
        shapes = []
        if not labels_data:
            return mask
        for label_row in labels_data:
            geom_str, type_id = label_row[1], label_row[2]
            if not isinstance(geom_str, str):
                continue
            try:
                coords_str_list = geom_str.split(',')
                if len(coords_str_list) < 6:
                    continue
                coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
                               for i in range(0, len(coords_str_list), 2)]
                if coords_list[0] != coords_list[-1]:
                    coords_list.append(coords_list[0])
                polygon = Polygon(coords_list)
                class_index = self.type_id_to_class_index.get(type_id)
                if class_index is not None:
                    shapes.append((polygon, int(class_index)))
            except (ValueError, IndexError):
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
            except ValueError:
                pass
        return mask

    def __len__(self):
        return 1

    def __getitem__(self, idx):
        if idx != 0:
            raise IndexError("此数据集仅包含一个项目")
        if self.image is None or self.label_mask is None:
            raise ValueError("图像或掩膜未正确加载")
        image_tensor = torch.from_numpy(self.image).float()
        mask_tensor = torch.from_numpy(self.label_mask).long()
        divisor = 32
        _, height, width = image_tensor.shape
        target_height = math.ceil(height / divisor) * divisor
        target_width = math.ceil(width / divisor) * divisor
        if height != target_height or width != target_width:
            pad_height = target_height - height
            pad_width = target_width - width
            pad_top, pad_bottom = pad_height // 2, pad_height - (pad_height // 2)
            pad_left, pad_right = pad_width // 2, pad_width - (pad_width // 2)
            padding = (pad_left, pad_right, pad_top, pad_bottom)
            image_tensor = F.pad(image_tensor, padding, mode='constant', value=0)
            mask_tensor = F.pad(mask_tensor.unsqueeze(0), padding, mode='constant', value=self.background_class_index).squeeze(0)
        return {"image": image_tensor, "mask": mask_tensor}

# -------------------- 掩膜转多边形函数 --------------------
def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
    """连接多个内孔到外边界"""
    if not interior_coords_list:
        return exterior_coords
    current_exterior = exterior_coords[:]
    exterior_index = rtree.index.Index()
    for idx, point in enumerate(current_exterior):
        exterior_index.insert(idx, (*point, *point))
    final_coords = list(current_exterior)
    remaining_interiors = interior_coords_list[:]
    while remaining_interiors:
        min_dist_sq = float('inf')
        best_exterior_pt_idx = best_interior_pt_idx = best_interior_hole_idx = -1
        for hole_idx, interior_coords in enumerate(remaining_interiors):
            for interior_pt_idx, (ix, iy) in enumerate(interior_coords):
                nearest_idx = list(exterior_index.nearest((ix, iy, ix, iy), 1))[0]
                ex, ey = final_coords[nearest_idx]
                dist_sq = (ix - ex)**2 + (iy - ey)**2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    best_exterior_pt_idx = nearest_idx
                    best_interior_pt_idx = interior_pt_idx
                    best_interior_hole_idx = hole_idx
        if best_exterior_pt_idx == -1:
            break
        chosen_interior = remaining_interiors.pop(best_interior_hole_idx)
        reordered_interior = chosen_interior[best_interior_pt_idx:] + chosen_interior[:best_interior_pt_idx]
        connection_point = final_coords[best_exterior_pt_idx]
        final_coords = (final_coords[:best_exterior_pt_idx+1] + reordered_interior + 
                        [reordered_interior[0], connection_point] + final_coords[best_exterior_pt_idx+1:])
        exterior_index = rtree.index.Index()
        for idx, point in enumerate(final_coords):
            exterior_index.insert(idx, (*point, *point))
    return final_coords

def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index, min_area=30):
    """将掩膜转换为多边形，处理孔洞"""
    segmentation_polygons = {}
    unique_classes = np.unique(mask)
    for class_index in unique_classes:
        if class_index == background_class_index:
            continue
        type_id = class_index_to_type_id.get(class_index)
        if type_id is None:
            continue
        class_mask = (mask == class_index).astype(np.uint8)
        contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None or len(contours) == 0:
            continue
        class_polygons_list = []
        i = 0
        while i >= 0:
            if hierarchy[0][i][3] == -1 and len(contours[i]) >= 3 and cv2.contourArea(contours[i]) >= min_area:
                exterior_geo_coords = [tuple(transform * (p[0][0], p[0][1])) for p in contours[i]]
                if exterior_geo_coords[0] != exterior_geo_coords[-1]:
                    exterior_geo_coords.append(exterior_geo_coords[0])
                interior_contours_geo = []
                hole_idx = hierarchy[0][i][2]
                while hole_idx != -1:
                    hole_contour = contours[hole_idx]
                    if len(hole_contour) >= 3 and cv2.contourArea(hole_contour) >= min_area:
                        interior_geo_coords = [tuple(transform * (p[0][0], p[0][1])) for p in hole_contour]
                        if interior_geo_coords[0] != interior_geo_coords[-1]:
                            interior_geo_coords.append(interior_geo_coords[0])
                        interior_contours_geo.append(interior_geo_coords)
                    hole_idx = hierarchy[0][hole_idx][0]
                final_boundary_coords = connect_multiple_holes(exterior_geo_coords, interior_contours_geo) if interior_contours_geo else exterior_geo_coords
                try:
                    final_polygon = Polygon(final_boundary_coords)
                    if not final_polygon.is_valid:
                        final_polygon = final_polygon.buffer(0)
                    if final_polygon.is_valid and not final_polygon.is_empty:
                        class_polygons_list.append(final_polygon)
                except Exception:
                    pass
            i = hierarchy[0][i][0]
        if class_polygons_list:
            segmentation_polygons[type_id] = class_polygons_list
    return segmentation_polygons

# -------------------- 主函数 --------------------
def main():
    # 配置
    TASK_ID = 133
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/test3.tif"
    if not os.path.exists(IMAGE_PATH):
        print(f"错误: 未找到图像文件 {IMAGE_PATH}")
        return
    batch_size = 1
    num_workers = 2
    max_epochs = 10
    learning_rate = 1e-3
    patience = 5
    fast_dev_run = False

    # 设置设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 连接数据库
    conn = connect_db()
    if conn is None:
        print("数据库连接失败，退出")
        return

    # 获取标签数据
    original_row_data = fetch_labels_from_db(conn, TASK_ID)
    if not original_row_data:
        print(f"未找到 task_id {TASK_ID} 的标签数据，退出")
        conn.close()
        return
    user_id, status = original_row_data[0][3], original_row_data[0][5]

    # 动态确定类别
    type_ids_from_db = sorted(list(set(row[2] for row in original_row_data)))
    num_classes = len(type_ids_from_db) + 1
    type_id_to_class_index = {type_id: index for index, type_id in enumerate(type_ids_from_db)}
    background_class_index = num_classes - 1
    class_index_to_type_id = {index: type_id for type_id, index in type_id_to_class_index.items()}

    # 创建数据集
    dataset = RemoteSensingSegmentationDataset(
        IMAGE_PATH, original_row_data, num_classes, type_id_to_class_index, background_class_index
    )
    dataloader = DataLoader(dataset, batch_size=batch_size, num_workers=num_workers, shuffle=False)

    # 获取图像通道数
    n_channels = dataset.image.shape[0]

    # 定义分割任务
    task = SemanticSegmentationTask(
        model='unet',
        backbone="resnet50",
        in_channels=n_channels,
        num_classes=num_classes,
        loss='ce',
        lr=learning_rate,
        patience=patience,
        weights=None,
    )

    # 配置训练器
    accelerator = 'gpu' if torch.cuda.is_available() else 'cpu'
    default_root_dir = os.path.join(tempfile.gettempdir(), 'torchgeo_experiments')
    os.makedirs(default_root_dir, exist_ok=True)
    trainer = Trainer(
        accelerator=accelerator,
        devices=1 if accelerator == 'gpu' else None,
        default_root_dir=default_root_dir,
        fast_dev_run=fast_dev_run,
        log_every_n_steps=1,
        min_epochs=1,
        max_epochs=max_epochs,
    )

    # 训练模型
    trainer.fit(model=task, train_dataloaders=dataloader, val_dataloaders=dataloader)

    # 预测
    predictions = trainer.predict(model=task, dataloaders=dataloader)
    if not predictions or not isinstance(predictions, list) or len(predictions) == 0:
        print("错误: 未返回预测结果")
        conn.close()
        return

    prediction_batch = predictions[0]
    if isinstance(prediction_batch, torch.Tensor):
        if prediction_batch.ndim == 4 and prediction_batch.shape[1] == num_classes:
            predicted_mask_tensor = torch.argmax(prediction_batch, dim=1)
            predicted_mask_np = predicted_mask_tensor.squeeze(0).cpu().numpy().astype(np.uint8)
        elif prediction_batch.ndim == 3:
            predicted_mask_np = prediction_batch.squeeze(0).cpu().numpy().astype(np.uint8)
        else:
            print("错误: 预测输出格式不符合预期")
            conn.close()
            return
    elif isinstance(prediction_batch, dict) and 'prediction' in prediction_batch:
        predicted_mask_tensor = prediction_batch['prediction']
        if predicted_mask_tensor.ndim == 4 and predicted_mask_tensor.shape[1] == num_classes:
            predicted_mask_tensor = torch.argmax(predicted_mask_tensor, dim=1)
        predicted_mask_np = predicted_mask_tensor.squeeze(0).cpu().numpy().astype(np.uint8)
    else:
        print("错误: 预测输出格式不符合预期")
        conn.close()
        return

    # 裁剪回原始尺寸
    original_height, original_width = dataset.image.shape[1], dataset.image.shape[2]
    padded_height, padded_width = predicted_mask_np.shape[0], predicted_mask_np.shape[1]
    if padded_height > original_height or padded_width > original_width:
        pad_height_total = padded_height - original_height
        pad_width_total = padded_width - original_width
        pad_top = pad_height_total // 2
        pad_left = pad_width_total // 2
        predicted_mask_np = predicted_mask_np[pad_top:pad_top + original_height, pad_left:pad_left + original_width]

    # 转换为多边形
    segmentation_polygons = identify_holes_and_split(
        predicted_mask_np, dataset.transform, class_index_to_type_id, background_class_index, min_area=1
    )

    # 更新数据库
    delete_existing_results_db(conn, TASK_ID)
    insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

    # 关闭连接
    conn.close()

if __name__ == "__main__":
    try:
        import rtree
        import cv2
        import shapely
        import lightning
        import torchgeo
        import psycopg2
        import rasterio
    except ImportError as e:
        print(f"缺少必需库: {e.name}。请安装。")
        print("尝试: pip install torchgeo rtree opencv-python shapely 'lightning>=2.0' psycopg2-binary rasterio")
        exit(1)
    main()