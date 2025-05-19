# utils.py
import json
import os
import shutil
import psycopg2
import rasterio
from shapely import MultiPolygon, unary_union
from shapely.geometry import Polygon, Point, mapping
import matplotlib.pyplot as plt
import cv2
from skimage.measure import regionprops, label
import torch
from torch.utils.data import Dataset, DataLoader
import rasterio.features
from scipy.stats import mode
import numpy as np
from PIL import Image
from rasterio.crs import CRS
from scipy.ndimage import generic_filter
from pyproj import Transformer
from scipy.ndimage import label as scipy_label
from rasterio.mask import mask
import torchvision.transforms as T
import torchvision.transforms.functional as TF
from numba import jit
from scipy.spatial import KDTree
# 数据库操作
def connect_db(host="localhost", dbname="label", user="postgres", password="123456", port="5432"):
    try:
        conn = psycopg2.connect(host=host, database=dbname, user=user, password=password, port=port)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None
    
def fetch_map_server_from_db(conn, task_id, TABLE_NAME2="task"):
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
    
def fetch_typeid_from_db(conn, task_id, table_name="task_accepted"):
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT type_arr FROM {table_name} WHERE task_id = %s"
        cursor.execute(query, (task_id,))
        type_arr = cursor.fetchall()
        cursor.close()
        return type_arr
    except psycopg2.Error as e:
        print(f"Error fetching type_id from database: {e}")
        return []

def fetch_labels_from_db(conn, task_id, table_name="mark"):
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        query = f"SELECT id, geom::json, type_id, user_id, task_id, status FROM {table_name} WHERE task_id = %s"
        cursor.execute(query, (task_id,))
        labels_data = cursor.fetchall()
        cursor.close()
        return labels_data
    except psycopg2.Error as e:
        print(f"Error fetching labels from database: {e}")
        return []

def delete_existing_results_db(conn, task_id, table_name="mark"):
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        delete_query = f"DELETE FROM {table_name} WHERE task_id = %s"
        cursor.execute(delete_query, (task_id,))
        conn.commit()
        print(f"已删除 task_id {task_id} 的原有数据。")
    except psycopg2.Error as e:
        print(f"Error deleting existing results from database: {e}")
        conn.rollback()
    finally:
        cursor.close()

def delete_point_results_db(conn, task_id, table_name="mark"):
    # 检查数据库连接是否有效
    if conn is None:
        return
    
    # 创建游标对象
    cursor = conn.cursor()
    
    try:
        # SQL 查询：删除 task_id 匹配且 geom 为点的记录
        delete_query = f"""
            DELETE FROM {table_name}
            WHERE task_id = %s
            AND geom LIKE '%%,%%'          -- 包含一个逗号（至少一个坐标对）
            AND geom NOT LIKE '%%,%%,%%'    -- 不包含两个或更多逗号（排除多坐标对）
        """
        # 执行删除操作，使用参数化查询防止 SQL 注入
        cursor.execute(delete_query, (task_id,))
        # 提交事务
        conn.commit()
        print(f"已删除 task_id {task_id} 的点标注数据。")
    
    except psycopg2.Error as e:
        # 捕获数据库错误并回滚事务
        print(f"Error deleting point results from database: {e}")
        conn.rollback()
    
    finally:
        # 关闭游标
        cursor.close()

def insert_segmentation_results_db(conn, task_id, segmentation_polygons, user_id, status, table_name="mark"):
    if conn is None:
        return
    cursor = conn.cursor()
    insert_query = f"INSERT INTO {table_name} (geom, type_id, user_id, task_id, status) VALUES %s"
    values_list = []
    for type_id, polygons in segmentation_polygons.items():
        for polygon in polygons:
            # Create GeoJSON format
            coords = [[x, y] for x, y in polygon.exterior.coords]
            geojson = {
                "type": "Polygon",
                "coordinates": [coords]
            }
            values_list.append((cursor.mogrify("(%s, %s, %s, %s, %s)", 
                                            (json.dumps(geojson), int(type_id), user_id, task_id, status)).decode('utf-8')))
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

# 数据集定义
class RemoteSensingSegmentationDataset(Dataset):
    def __init__(self, image_path, labels_data=None, num_classes=None, type_id_to_class_index=None, 
                 background_class_index=None, model_scope_str=None, apply_transforms=True):
        self.image_path = image_path
        self.labels_data = labels_data
        self.num_classes = num_classes
        self.type_id_to_class_index = type_id_to_class_index
        self.background_class_index = background_class_index
        self.model_scope_polygons = parse_model_scope(model_scope_str) if model_scope_str else None
        self.apply_transforms = apply_transforms

        # 加载图像和变换信息
        self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)

        # 处理模型作用范围
        if self.model_scope_polygons:
            self.scope_mask = create_scope_mask(self.model_scope_polygons, self.transform, 
                                              self.image.shape[1], self.image.shape[2])
            if labels_data is not None and num_classes is not None:
                self.full_label_mask = self._create_label_mask(labels_data, self.transform, 
                                                             self.image.shape[1], self.image.shape[2])
                self.image, self.label_mask = apply_scope_to_image_and_mask(self.image, self.full_label_mask, 
                                                                          self.scope_mask)
            else:
                self.image, _ = apply_scope_to_image_and_mask(self.image, None, self.scope_mask)
                self.label_mask = None
        else:
            if labels_data is not None and num_classes is not None:
                self.label_mask = self._create_label_mask(labels_data, self.transform, 
                                                        self.image.shape[1], self.image.shape[2])
            else:
                self.label_mask = None

        # 定义几何变换（仅在训练时应用）
        if self.apply_transforms:
            self.transform_pipeline = T.Compose([
                T.RandomHorizontalFlip(p=0.5),          # 50%概率水平翻转
                T.RandomVerticalFlip(p=0.5),            # 50%概率垂直翻转
                T.RandomRotation(degrees=(-45, 45), fill=(self.background_class_index,)),    # 随机旋转-45到45度
                # T.RandomResizedCrop(size=(256, 256), scale=(0.8, 1.2)),  # 随机裁剪并缩放到256x256
            ])
        else:
            self.transform_pipeline = None

    def _load_image(self, image_path):
        with rasterio.open(image_path) as src:
            image = src.read()  # (C, H, W)
            transform = src.transform
            bounds = src.bounds
            crs = src.crs
            if crs != 'EPSG:3857':
                print(f"警告: 图像坐标系为 {crs}，不是 EPSG:3857，可能导致掩膜生成错误！")
        image = image.astype(np.float32) / 255.0
        return image, transform, bounds, crs

    def _create_label_mask(self, labels_data, transform, img_height, img_width):
        # 保持原有逻辑
        mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)
        shapes = []
        for _, geom_str, type_id, *_ in labels_data:
            coords_str_list = geom_str.split(',')
            coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
                           for i in range(0, len(coords_str_list), 2)]
            polygon = Polygon(coords_list)
            class_index = self.type_id_to_class_index.get(type_id)
            if class_index is not None:
                shapes.append((polygon, int(class_index)))
        if shapes:
            mask = rasterio.features.rasterize(
                shapes=shapes,
                out_shape=(img_height, img_width),
                fill=self.background_class_index,
                transform=transform,
                all_touched=True,
                dtype=np.uint8
            )
        return mask

    def __len__(self):
        return 1  # 单张图像数据集

    def __getitem__(self, idx):
        if self.image is None or (self.label_mask is None and self.labels_data is not None):
            raise ValueError("Image or label mask is None.")

        image = torch.from_numpy(self.image).float()
        label_mask = torch.from_numpy(self.label_mask).long() if self.label_mask is not None else None

        # 应用几何变换（仅在训练时）
        if self.apply_transforms and self.transform_pipeline is not None and label_mask is not None:
            # 确保图像和标签同时变换
            seed = torch.random.initial_seed()  # 同步随机种子
            torch.manual_seed(seed)
            image = self.transform_pipeline(image)
            torch.manual_seed(seed)
            label_mask = self.transform_pipeline(label_mask.unsqueeze(0).float()).squeeze(0).long()

        return image, label_mask
''''新增数据增强几何变换'''
# class RemoteSensingSegmentationDataset(Dataset):
#     def __init__(self, image_path, labels_data=None, num_classes=None, type_id_to_class_index=None, 
#                  background_class_index=None, model_scope_str=None):
#         self.image_path = image_path
#         self.labels_data = labels_data
#         self.num_classes = num_classes
#         self.type_id_to_class_index = type_id_to_class_index
#         self.background_class_index = background_class_index
#         self.model_scope_polygons = parse_model_scope(model_scope_str) if model_scope_str else None
#         self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)

#         if self.model_scope_polygons:
#             self.scope_mask = create_scope_mask(self.model_scope_polygons, self.transform, 
#                                               self.image.shape[1], self.image.shape[2])

#             # 如果有标签数据，创建完整标签掩码
#             self.full_label_mask = None
#             if labels_data is not None and num_classes is not None and type_id_to_class_index is not None and background_class_index is not None:
#                 self.full_label_mask = self._create_label_mask(labels_data, self.transform, 
#                                                              self.image.shape[1], self.image.shape[2])
#                 # 根据作用范围裁剪图像和掩码
#                 self.image, self.label_mask = apply_scope_to_image_and_mask(self.image, self.full_label_mask, 
#                                                                           self.scope_mask)
#             else:
#                 self.image, _ = apply_scope_to_image_and_mask(self.image, None, self.scope_mask)
#                 self.label_mask = None
#         else:
#             if labels_data is not None and num_classes is not None and type_id_to_class_index is not None and background_class_index is not None:
#                 self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])
#             else:
#                 self.label_mask = None
        
#         # # 创建作用范围掩码
#         # self.scope_mask = create_scope_mask(self.model_scope_polygons, self.transform, 
#         #                                   self.image.shape[1], self.image.shape[2])
        
#         # # 如果有标签数据，创建完整标签掩码
#         # self.full_label_mask = None
#         # if labels_data is not None and num_classes is not None and type_id_to_class_index is not None and background_class_index is not None:
#         #     self.full_label_mask = self._create_label_mask(labels_data, self.transform, 
#         #                                                  self.image.shape[1], self.image.shape[2])
#         #     # 根据作用范围裁剪图像和掩码
#         #     self.image, self.label_mask = apply_scope_to_image_and_mask(self.image, self.full_label_mask, 
#         #                                                               self.scope_mask)
#         # else:
#         #     self.image, _ = apply_scope_to_image_and_mask(self.image, None, self.scope_mask)
#         #     self.label_mask = None
#     # def __init__(self, image_path, labels_data=None, num_classes=None, type_id_to_class_index=None, background_class_index=None):
#     #     self.image_path = image_path
#     #     self.labels_data = labels_data
#     #     self.num_classes = num_classes
#     #     self.type_id_to_class_index = type_id_to_class_index
#     #     self.background_class_index = background_class_index
#     #     self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)
#     #     if labels_data is not None and num_classes is not None and type_id_to_class_index is not None and background_class_index is not None:
#     #         self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])
#     #     else:
#     #         self.label_mask = None
#     # def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index, background_class_index):
#     #     self.image_path = image_path
#     #     self.labels_data = labels_data
#     #     self.num_classes = num_classes
#     #     self.type_id_to_class_index = type_id_to_class_index
#     #     self.background_class_index = background_class_index
#     #     self.image, self.transform, self.bounds, self.crs = self._load_image(image_path)
#     #     self.label_mask = self._create_label_mask(labels_data, self.transform, self.image.shape[1], self.image.shape[2])
#     #     # 验证尺寸一致性
#     #     if self.image.shape[1:] != self.label_mask.shape:
#     #         raise ValueError(f"Image shape {self.image.shape[1:]} does not match mask shape {self.label_mask.shape}")

#     def _load_image(self, image_path):
#         try:
#             with rasterio.open(image_path) as src:
#                 image = src.read()  # (C, H, W)
#                 transform = src.transform
#                 bounds = src.bounds
#                 crs = src.crs
#                 if crs != 'EPSG:3857':
#                     print(f"警告: 图像坐标系为 {crs}，不是 EPSG:3857，可能导致掩膜生成错误！")
#             image = image.astype(np.float32) / 255.0
#             print(f"Loaded image shape: {image.shape}")
#             return image, transform, bounds, crs
#         except rasterio.RasterioIOError as e:
#             print(f"Error loading image: {e}")
#             return None, None, None, None

#     def _create_label_mask(self, labels_data, transform, img_height, img_width):
#         mask = np.full((img_height, img_width), self.background_class_index, dtype=np.uint8)
#         shapes = []
#         for _, geom_str, type_id, *_ in labels_data:
#             try:
#                 coords_str_list = geom_str.split(',')
#                 coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
#                                for i in range(0, len(coords_str_list), 2)]
#                 polygon = Polygon(coords_list)
#                 class_index = self.type_id_to_class_index.get(type_id)
#                 if class_index is not None:
#                     shapes.append((polygon, int(class_index)))
#             except (ValueError, IndexError) as e:
#                 print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
#                 continue
#         if shapes:
#             mask = rasterio.features.rasterize(
#                 shapes=shapes,
#                 out_shape=(img_height, img_width),
#                 fill=self.background_class_index,
#                 transform=transform,
#                 all_touched=True,
#                 dtype=np.uint8
#             )
#         print(f"Created mask shape: {mask.shape}")
#         return mask

#     def __len__(self):
#         return 1

#     def __getitem__(self, idx):
#         if self.image is None or self.label_mask is None:
#             raise ValueError("Image or label mask is None.")
#         return torch.from_numpy(self.image).float(), torch.from_numpy(self.label_mask).long()
    
def parse_model_scope(model_scope_str):
    """解析模型作用范围字符串，返回地理坐标的多边形列表"""
    try:
        model_scope = json.loads(model_scope_str)
        if not model_scope:
            return None
        polygons = []
        for scope_group in model_scope:
            for scope in scope_group:  # 处理嵌套结构
                coords = [(x, y) for x, y in scope]
                polygons.append(Polygon(coords))
        return polygons
    except json.JSONDecodeError as e:
        print(f"Error decoding model scope: {e}")
        return None

def create_scope_mask(polygons, transform, img_height, img_width):
    """根据模型作用范围创建二值掩码，1表示作用区域，0表示非作用区域"""
    mask = np.zeros((img_height, img_width), dtype=np.uint8)
    if polygons is None:
        return np.ones((img_height, img_width), dtype=np.uint8)  # 如果没有范围，全部为1
    shapes = [(poly, 1) for poly in polygons]
    mask = rasterio.features.rasterize(
        shapes=shapes,
        out_shape=(img_height, img_width),
        fill=0,
        transform=transform,
        all_touched=True,
        dtype=np.uint8
    )
    # 扩展作用范围到图像边界
    from scipy.ndimage import binary_dilation
    mask = binary_dilation(mask, iterations=5)  # 扩展5像素
    return mask

def apply_scope_to_image_and_mask(image, label_mask, scope_mask):
    """根据作用范围裁剪图像和掩码，只保留作用区域内的像素"""
    if scope_mask is None or np.all(scope_mask == 1):
        return image, label_mask
    
    # 对图像应用掩码
    masked_image = image.copy()
    for c in range(image.shape[0]):  # 对每个通道
        masked_image[c] = masked_image[c] * scope_mask
    
    # 如果 label_mask 为 None，直接返回 None
    if label_mask is None:
        return masked_image, None
    
    # 对标签掩码应用掩码，非作用区域设置为背景
    masked_label = label_mask.copy()
    background_index = np.max(label_mask)  # 假设背景是最大值
    masked_label[scope_mask == 0] = background_index
    
    return masked_image, masked_label

# 掩膜处理
def connect_multiple_holes(exterior_coords, interior_coords_list):
    """
    将多个内环连接到外环，使用 KD 树找到内环与外环的最近点对。
    
    参数:
        exterior_coords: 外环坐标列表，例如 [(x1, y1), (x2, y2), ...]
        interior_coords_list: 内环坐标列表的列表，例如 [[(x1, y1), ...], [(x2, y2), ...]]
    
    返回:
        连接所有内环后的外环坐标列表
    """
    # 简化内外环坐标(每隔1个点保留一个点)
    simplified_exterior = exterior_coords[::2]
    simplified_interior_list = [interior[::2] for interior in interior_coords_list]
    
    # 初始化当前外环
    # simplified_exterior = exterior_coords
    # simplified_interior_list = [interior for interior in interior_coords_list]
    current_exterior = simplified_exterior[:]
    
    # 遍历每个内环
    for interior_coords in simplified_interior_list:
        # 将当前外环坐标转换为 NumPy 数组，用于 KD 树
        exterior_points = np.array(current_exterior)
        # 构建 KD 树
        kd_tree = KDTree(exterior_points)
        
        # 初始化最小距离和最佳连接点索引
        min_dist = float('inf')
        best_exterior_idx = 0
        best_interior_idx = 0
        
        # 遍历内环上的每个点
        for i, interior_point in enumerate(interior_coords):
            # 使用 KD 树查询距离外环最近的点
            dist, nearest_idx = kd_tree.query(interior_point)
            if dist < min_dist:
                min_dist = dist
                best_exterior_idx = nearest_idx
                best_interior_idx = i
        
        # 将内环连接到外环
        interior_part = interior_coords[best_interior_idx:] + interior_coords[:best_interior_idx]
        new_exterior = (current_exterior[:best_exterior_idx + 1] + 
                        interior_part + 
                        [interior_coords[best_interior_idx]] + 
                        current_exterior[best_exterior_idx:])
        current_exterior = new_exterior
    
    return current_exterior

def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index):
    """
    从掩码中识别多边形（包括外环和内环），并将内环连接到外环。
    
    参数:
        mask: 输入的掩码图像 (numpy 数组)
        transform: 坐标变换函数
        class_index_to_type_id: 类索引到类型 ID 的映射字典
        background_class_index: 背景类索引
    
    返回:
        字典，键为类型 ID，值为对应类型的多边形列表
    """
    polygons = {}
    for class_index in np.unique(mask):
        if class_index == background_class_index:
            continue
        type_id = class_index_to_type_id.get(class_index)
        if type_id is None:
            continue
        # 创建当前类的掩码
        class_mask = (mask == class_index).astype(np.uint8)
        # 查找轮廓和层级关系
        contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None or len(contours) == 0:
            continue
        class_polygons = []
        i = 0
        while i < len(contours):
            if len(contours[i]) < 3:
                i += 1
                continue
            # 如果是外环（无父轮廓）
            if hierarchy[0][i][3] == -1:
                # 获取外环坐标并应用变换
                exterior_coords = [(transform * (point[0][0], point[0][1])) for point in contours[i]]
                exterior_coords = [(x, y) for x, y in exterior_coords]
                interior_contours = []
                # 查找所有内环
                hole_idx = hierarchy[0][i][2]
                while hole_idx != -1:
                    if len(contours[hole_idx]) >= 3:
                        interior_coords = [(transform * (point[0][0], point[0][1])) for point in contours[hole_idx]]
                        interior_coords = [(x, y) for x, y in interior_coords]
                        interior_contours.append(interior_coords)
                    hole_idx = hierarchy[0][hole_idx][0]
                # 连接内环到外环（如果有内环）
                final_coords = connect_multiple_holes(exterior_coords, interior_contours) if interior_contours else exterior_coords
                try:
                    polygon = Polygon(final_coords)
                    class_polygons.append(polygon)
                except Exception as e:
                    print(f"创建多边形时出错: {e}")
            i += 1
        if class_polygons:
            polygons[type_id] = class_polygons
    return polygons

# def connect_multiple_holes(exterior_coords, interior_coords_list):
#     current_exterior = exterior_coords[:]
#     exterior_index = rtree.index.Index()
#     for idx, (x, y) in enumerate(current_exterior):
#         exterior_index.insert(idx, (x, y, x, y))
    
#     for interior_coords in interior_coords_list:
#         min_dist = float('inf')
#         best_exterior_idx = 0
#         best_interior_idx = 0
#         for i, (ix, iy) in enumerate(interior_coords):
#             nearest_idx = list(exterior_index.nearest((ix, iy, ix, iy), 1))[0]
#             ex, ey = current_exterior[nearest_idx]
#             dist = ((ix - ex) ** 2 + (iy - ey) ** 2) ** 0.5
#             if dist < min_dist:
#                 min_dist = dist
#                 best_exterior_idx = nearest_idx
#                 best_interior_idx = i
#         new_exterior = current_exterior[:best_exterior_idx + 1] + \
#                        (interior_coords[best_interior_idx:] + interior_coords[:best_interior_idx]) + \
#                        [interior_coords[best_interior_idx]] + \
#                        current_exterior[best_exterior_idx:]
#         current_exterior = new_exterior
#         exterior_index = rtree.index.Index()
#         for j, (x, y) in enumerate(current_exterior):
#             exterior_index.insert(j, (x, y, x, y))
#     return current_exterior

# def identify_holes_and_split(mask, transform, class_index_to_type_id, background_class_index):
#     polygons = {}
#     for class_index in np.unique(mask):
#         if class_index == background_class_index:
#             continue
#         type_id = class_index_to_type_id.get(class_index)
#         if type_id is None:
#             continue
#         class_mask = (mask == class_index).astype(np.uint8)
#         contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
#         if hierarchy is None or len(contours) == 0:
#             continue
#         class_polygons = []
#         i = 0
#         while i < len(contours):
#             if len(contours[i]) < 3:
#             # if len(contours[i]) < 3 or cv2.contourArea(contours[i]) < min_area:
#                 i += 1
#                 continue
#             if hierarchy[0][i][3] == -1:
#                 exterior_coords = [(transform * (point[0][0], point[0][1])) for point in contours[i]]
#                 exterior_coords = [(x, y) for x, y in exterior_coords]
#                 interior_contours = []
#                 hole_idx = hierarchy[0][i][2]
#                 while hole_idx != -1:
#                     if len(contours[hole_idx]) >= 3:
#                     # if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
#                         interior_coords = [(transform * (point[0][0], point[0][1])) for point in contours[hole_idx]]
#                         interior_coords = [(x, y) for x, y in interior_coords]
#                         interior_contours.append(interior_coords)
#                     hole_idx = hierarchy[0][hole_idx][0]
#                 final_coords = connect_multiple_holes(exterior_coords, interior_contours) if interior_contours else exterior_coords
#                 try:
#                     polygon = Polygon(final_coords)
#                     class_polygons.append(polygon)
#                 except Exception as e:
#                     print(f"创建多边形时出错: {e}")
#             i += 1
#         if class_polygons:
#             polygons[type_id] = class_polygons
#     return polygons

# def post_process_mask(mask, min_object_size=10, hole_size_threshold=20, boundary_smoothing=3, mode_filter_size=3):
#     """
#     对输入掩码进行后处理，包括移除小对象、填充小孔洞、平滑边界和众数滤波。
    
#     参数：
#         mask: 输入的多类别掩码，numpy 数组，uint8 类型
#         min_object_size: 最小对象面积阈值，小于此值的对象将被移除
#         hole_size_threshold: 小孔洞面积阈值，小于此值的孔洞将被填充
#         boundary_smoothing: 形态学平滑的核大小
#         mode_filter_size: 众数滤波的窗口大小
    
#     返回：
#         processed_mask: 处理后的掩码，numpy 数组，uint8 类型
#     """
#     # 复制原始掩码并初始化输出掩码
#     original_mask = mask.copy().astype(np.uint8)
#     unique_classes = np.unique(mask)
#     processed_mask = np.zeros_like(mask, dtype=np.uint8)
    
#     # 检查 GPU 可用性
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"Using device: {device}")
    
#     # 第一步：逐类别处理小对象移除、孔洞填充和形态学平滑
#     for class_idx in unique_classes:
#         if class_idx == 0:  # 跳过背景
#             continue
            
#         # 提取当前类别的二值掩码
#         class_mask = (mask == class_idx).astype(np.uint8)
#         labeled_mask = label(class_mask)
#         properties = regionprops(labeled_mask)
        
#         # 移除小对象
#         for prop in properties:
#             if prop.area < min_object_size:
#                 labeled_mask[labeled_mask == prop.label] = 0
#         cleaned_mask = (labeled_mask > 0).astype(np.uint8)
        
#         # 填充小孔洞
#         filled_mask = cleaned_mask.copy()
#         contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
#         for contour in contours:
#             temp_mask = np.zeros_like(cleaned_mask)
#             cv2.drawContours(temp_mask, [contour], 0, 1, -1)
#             temp_mask_inv = 1 - temp_mask
#             holes = label(temp_mask_inv)
#             hole_props = regionprops(holes)
#             for hole in hole_props:
#                 if 0 < hole.area < hole_size_threshold:
#                     filled_mask[holes == hole.label] = 1
        
#         # 形态学平滑
#         kernel = np.ones((boundary_smoothing, boundary_smoothing), np.uint8)
#         smoothed_mask = cv2.morphologyEx(filled_mask, cv2.MORPH_CLOSE, kernel)
#         smoothed_mask = cv2.morphologyEx(smoothed_mask, cv2.MORPH_OPEN, kernel)
        
#         # 将处理后的掩码添加到总掩码中
#         processed_mask[smoothed_mask == 1] = class_idx
    
#     # 第二步：全局众数滤波（使用 scipy 的 generic_filter）
#     def mode_function(window):
#         values, counts = np.unique(window, return_counts=True)
#         if len(counts) == 0:
#             return 0  # 空窗口返回背景
#         return values[np.argmax(counts)]

#     final_mask = generic_filter(
#         processed_mask,
#         mode_function,
#         size=mode_filter_size,
#         mode='nearest'
#     ).astype(np.uint8)
    
#     return final_mask

@jit(nopython=True)
def remove_small_objects(labeled_mask, min_object_size):
    """
    使用Numba从标记的掩码中移除小于min_object_size的对象。

    参数：
        labeled_mask: 整数标签的二维numpy数组
        min_object_size: 对象的最小面积阈值

    返回值：
        labeled_mask: 修改后的掩码，移除了小对象
    """
    # 找到最大的标签
    max_label = 0
    for i in range(labeled_mask.shape[0]):
        for j in range(labeled_mask.shape[1]):
            if labeled_mask[i, j] > max_label:
                max_label = labeled_mask[i, j]

    # 统计每个标签的像素数量
    label_counts = np.zeros(max_label + 1, dtype=np.int32)
    for i in range(labeled_mask.shape[0]):
        for j in range(labeled_mask.shape[1]):
            label = labeled_mask[i, j]
            if label > 0:
                label_counts[label] += 1

    # 移除小对象
    for i in range(labeled_mask.shape[0]):
        for j in range(labeled_mask.shape[1]):
            label = labeled_mask[i, j]
            if label > 0 and label_counts[label] < min_object_size:
                labeled_mask[i, j] = 0

    return labeled_mask

def post_process_mask(mask, min_object_size=10, hole_size_threshold=20, boundary_smoothing=3):
    """
    通过移除小对象、填充小孔和平滑边界来后处理输入掩码。

    参数：
        mask: 输入的多类别掩码，numpy数组，uint8类型
        min_object_size: 最小对象面积阈值；小于此值的对象将被移除
        hole_size_threshold: 小孔面积阈值；小于此值的孔将被填充
        boundary_smoothing: 形态学平滑的内核大小

    返回值：
        processed_mask: 处理后的掩码，numpy数组，uint8类型
    """
    # 复制原始掩码并初始化输出掩码
    original_mask = mask.copy().astype(np.uint8)
    unique_classes = np.unique(mask)
    processed_mask = np.zeros_like(mask, dtype=np.uint8)

    # 步骤 1: 处理每个类别，以移除小对象、填充孔和平滑边界
    for class_idx in unique_classes:
        if class_idx == 0:  # 跳过背景
            continue

        # 提取当前类别的二值掩码
        class_mask = (mask == class_idx).astype(np.uint8)
        labeled_mask, num_labels = label(class_mask, return_num=True)

        # 使用Numba移除小对象
        labeled_mask = remove_small_objects(labeled_mask, min_object_size)
        cleaned_mask = (labeled_mask > 0).astype(np.uint8)

        # 填充小孔
        filled_mask = cleaned_mask.copy()
        contours, hierarchy = cv2.findContours(cleaned_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        for i, contour in enumerate(contours):
            if hierarchy[0][i][3] != -1:  # 如果有父轮廓，说明是内部孔洞
                area = cv2.contourArea(contour)
                if 0 < area < hole_size_threshold:
                    cv2.drawContours(filled_mask, [contour], 0, 1, -1)
        # filled_mask = cleaned_mask.copy()
        # contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # for contour in contours:
        #     temp_mask = np.zeros_like(cleaned_mask)
        #     cv2.drawContours(temp_mask, [contour], 0, 1, -1)
        #     temp_mask_inv = 1 - temp_mask
        #     holes = label(temp_mask_inv)
        #     hole_props = regionprops(holes)
        #     for hole in hole_props:
        #         if 0 < hole.area < hole_size_threshold:
        #             filled_mask[holes == hole.label] = 1

        # 形态学平滑
        # kernel = np.ones((boundary_smoothing, boundary_smoothing), np.uint8)
        # smoothed_mask = cv2.morphologyEx(filled_mask, cv2.MORPH_CLOSE, kernel)
        # smoothed_mask = cv2.morphologyEx(smoothed_mask, cv2.MORPH_OPEN, kernel)

        # 将处理后的掩码添加到总掩码
        # processed_mask[smoothed_mask == 1] = class_idx
        processed_mask[filled_mask == 1] = class_idx
    # visualize_mask_comparison(original_mask, processed_mask)
    return processed_mask

# def post_process_mask(mask, min_object_size=10, hole_size_threshold=20, boundary_smoothing=3, mode_filter_size=3):
#     original_mask = mask.copy().astype(np.uint8)
#     unique_classes = np.unique(mask)
#     processed_mask = np.zeros_like(mask, dtype=np.uint8)
    
#     # 检查是否有 GPU 可用
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"Using device: {device}")
    
#     for class_idx in unique_classes:
#         if class_idx == 0:  # 跳过背景
#             continue
            
#         class_mask = (mask == class_idx).astype(np.uint8)
#         labeled_mask = label(class_mask)
#         properties = regionprops(labeled_mask)
        
#         # 移除小对象
#         for prop in properties:
#             if prop.area < min_object_size:
#                 labeled_mask[labeled_mask == prop.label] = 0
#         cleaned_mask = (labeled_mask > 0).astype(np.uint8)
        
#         # 填充小孔洞
#         filled_mask = cleaned_mask.copy()
#         contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
#         for contour in contours:
#             temp_mask = np.zeros_like(cleaned_mask)
#             cv2.drawContours(temp_mask, [contour], 0, 1, -1)
#             temp_mask_inv = 1 - temp_mask
#             holes = label(temp_mask_inv)
#             hole_props = regionprops(holes)
#             for hole in hole_props:
#                 if hole.area < hole_size_threshold and hole.area > 0:
#                     filled_mask[holes == hole.label] = 1
        
#         # 现有的形态学平滑
#         kernel = np.ones((boundary_smoothing, boundary_smoothing), np.uint8)
#         smoothed_mask = cv2.morphologyEx(filled_mask, cv2.MORPH_CLOSE, kernel)
#         smoothed_mask = cv2.morphologyEx(smoothed_mask, cv2.MORPH_OPEN, kernel)
        
#         # 使用 PyTorch 实现众数滤波
#         smoothed_tensor = torch.from_numpy(smoothed_mask).float().to(device)
#         pad_size = mode_filter_size // 2
#         padded_tensor = torch.nn.functional.pad(smoothed_tensor[None, None, :, :], 
#                                                (pad_size, pad_size, pad_size, pad_size), 
#                                                mode='replicate')[0, 0]  # [H, W]
        
#         # 展开滑动窗口
#         unfolded = torch.nn.functional.unfold(
#             padded_tensor[None, None, :, :],  # [1, 1, H, W]
#             kernel_size=(mode_filter_size, mode_filter_size),
#             stride=1
#         )  # [1, mode_filter_size*mode_filter_size, H*W]
        
#         # 计算每个窗口的众数
#         unfolded = unfolded.view(mode_filter_size * mode_filter_size, -1).long()  # [window_size, num_patches]
#         mode_filtered = torch.mode(unfolded, dim=0)[0]  # 沿窗口维度计算众数
#         mode_filtered = mode_filtered.view(smoothed_mask.shape).cpu().numpy().astype(np.uint8)
        
#         # 高斯模糊作为最终平滑步骤
#         blurred = cv2.GaussianBlur(mode_filtered.astype(np.float32), (5, 5), 0)
#         smoothed_mask = (blurred > 0.5).astype(np.uint8)
        
#         processed_mask[smoothed_mask == 1] = class_idx
    
#     visualize_mask_comparison(original_mask, processed_mask)
#     return processed_mask


def create_original_label_mask(labels_data, transform, img_height, img_width, background_class_index, type_id_to_class_index):
    """根据标签数据创建标签掩膜，使用地理坐标，后面的多边形覆盖前面的"""
    mask = np.full((img_height, img_width), background_class_index, dtype=np.uint8)
    for _, geom_str, type_id, *_ in labels_data:
        try:
            coords_str_list = geom_str.split(',')
            coords_list = []
            for i in range(0, len(coords_str_list), 2):
                x = float(coords_str_list[i].strip())
                y = float(coords_str_list[i+1].strip())
                coords_list.append((x, y))
            polygon = Polygon(coords_list)
            class_index = type_id_to_class_index.get(type_id)
            if class_index is not None:
                temp_mask = rasterio.features.rasterize(
                    shapes=[(polygon, int(class_index))],
                    out_shape=(img_height, img_width),
                    fill=background_class_index,
                    transform=transform,
                    all_touched=True,
                    dtype=np.uint8
                )
                # 覆盖逻辑：非背景区域用新值替换
                mask = np.where(temp_mask != background_class_index, temp_mask, mask)
            else:
                print(f"警告: type_id {type_id} 未在映射中找到，已跳过。")
        except (ValueError, IndexError) as e:
            print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
            continue
        except ValueError as e:
            print(f"光栅化多边形时出错: {e}")
            continue
    return mask

# 可视化函数
def visualize_mask_comparison(original_mask, processed_mask):
    plt.figure(figsize=(15, 5))
    plt.subplot(131)
    plt.imshow(original_mask, cmap='tab20')
    plt.title("Raw Predicted Mask")
    plt.axis('off')
    plt.subplot(132)
    plt.imshow(processed_mask, cmap='tab20')
    plt.title("Post-Processed Mask")
    plt.axis('off')
    difference = np.zeros_like(original_mask)
    difference[(original_mask != processed_mask) & (original_mask > 0)] = 1
    difference[(original_mask != processed_mask) & (processed_mask > 0) & (original_mask == 0)] = 2
    plt.subplot(133)
    plt.imshow(difference, cmap='coolwarm')
    plt.title("Changes (Red: Removed, Blue: Added)")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig("mask_processing_comparison.png")
    plt.close()
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

def visualize_results(image_np, label_mask_np, predicted_mask_np, num_classes, output_path_prefix="segmentation_result"):
    class_colors = plt.cm.get_cmap('tab20', num_classes)
    colored_label_mask = class_colors(label_mask_np / num_classes)[:, :, :3]
    colored_predicted_mask = class_colors(predicted_mask_np / num_classes)[:, :, :3]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    axes[0].imshow(np.transpose(image_np[:3, :, :], (1, 2, 0)))
    axes[0].set_title("Original Image (RGB)")
    axes[1].imshow(colored_label_mask)
    axes[1].set_title("Ground Truth Mask")
    axes[2].imshow(colored_predicted_mask)
    axes[2].set_title("Predicted Mask")
    plt.tight_layout()
    plt.savefig(f"{output_path_prefix}_masks.png")
    plt.close()
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(np.transpose(image_np[:3, :, :], (1, 2, 0)))
    ax.imshow(colored_predicted_mask, alpha=0.5)
    ax.set_title("Segmentation Overlay")
    plt.tight_layout()
    plt.savefig(f"{output_path_prefix}_overlay.png")
    plt.close()
    print(f"可视化结果已保存到 {output_path_prefix}_*.png")

def visualize_original_mask(mask, num_classes, output_path="original_mask.png"):
    class_colors = plt.cm.get_cmap('tab20', num_classes)
    colored_mask = class_colors(mask / num_classes)[:, :, :3]
    plt.figure(figsize=(8, 8))
    plt.imshow(colored_mask)
    plt.title("Original Mask from Database")
    plt.axis('off')
    plt.savefig(output_path)
    plt.close()
    print(f"Original mask visualization saved to {output_path}")

# 数据准备
def prepare_data_for_sklearn(image, mask):
    X = image.transpose(1, 2, 0).reshape(-1, image.shape[0])
    y = mask.ravel()
    return X, y

#目标检测 yolo 模型设置
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
def create_yolo_dataset(labels_data, image_path, output_dir, model_scope_str=None):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    images_dir = os.path.join(output_dir, "images")
    labels_dir = os.path.join(output_dir, "labels")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)

    # 解析模型作用范围
    model_scope_polygons = parse_model_scope(model_scope_str) if model_scope_str else None
    # 过滤标注
    filtered_labels = filter_labels_by_scope(labels_data, model_scope_polygons)

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
        for _, geom_str, type_id, *_ in filtered_labels:
            try:
                if type_id not in type_id_to_class_id:
                    type_id_to_class_id[type_id] = class_id_counter
                    class_id_counter += 1
                class_id = type_id_to_class_id[type_id]

                coords_str_list = geom_str.split(',')
                coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
                               for i in range(0, len(coords_str_list), 2)]
                polygon = Polygon(coords_list)
                coords = list(polygon.exterior.coords)[:-1]  # 移除闭合点

                pixel_coords = [inverse_transform * (x, y) for x, y in coords]
                pixel_coords = [(x * width_ratio, y * height_ratio) for x, y in pixel_coords]

                if len(pixel_coords) < 4:
                    print(f"警告: 多边形点数少于4，跳过: {geom_str}")
                    continue

                norm_coords = [(x / img_width, y / img_height) for x, y in pixel_coords[:4]]
                norm_coords = [max(0, min(1, coord)) for sublist in norm_coords for coord in sublist]

                f.write(f"{class_id} {' '.join(map(str, norm_coords))}\n")

                obb_box = [coord for point in pixel_coords[:4] for coord in point]
                original_boxes.append(obb_box)
                original_labels.append(f"Class {class_id}")
            except Exception as e:
                print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
                continue

    return images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels
# def create_yolo_dataset(labels_data, image_path, output_dir):
#     """从数据库提取标注，生成 YOLO OBB 格式的数据集，并返回标注框用于可视化"""
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
#                 coords = list(polygon.exterior.coords)[:-1]  # Remove duplicate closing point

#                 # Convert to pixel coordinates
#                 pixel_coords = [inverse_transform * (x, y) for x, y in coords]
#                 pixel_coords = [(x * width_ratio, y * height_ratio) for x, y in pixel_coords]

#                 # Ensure we have at least 4 points for a valid OBB
#                 if len(pixel_coords) < 4:
#                     print(f"警告: 多边形点数少于4，跳过: {geom_str}")
#                     continue

#                 # Normalize coordinates to [0, 1]
#                 norm_coords = [(x / img_width, y / img_height) for x, y in pixel_coords[:4]]  # Take first 4 points for OBB
#                 norm_coords = [max(0, min(1, coord)) for sublist in norm_coords for coord in sublist]  # Flatten and clamp

#                 # Write in YOLO OBB format: class_id x1 y1 x2 y2 x3 y3 x4 y4
#                 f.write(f"{class_id} {' '.join(map(str, norm_coords))}\n")

#                 # For visualization (use pixel coordinates)
#                 obb_box = [coord for point in pixel_coords[:4] for coord in point]  # Flatten to [x1, y1, x2, y2, x3, y3, x4, y4]
#                 original_boxes.append(obb_box)
#                 original_labels.append(f"Class {class_id}")

#             except Exception as e:
#                 print(f"处理几何字符串时出错: {e}, geom_str: {geom_str}")
#                 continue

#     return images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels

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
def process_yolo_results(results, transform, task_id, user_id, status, conn, class_id_to_type_id, output_image_path,IMAGE_PATH):
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
# 处理重叠标注
def filter_original_labels(original_polygons_with_type, predicted_polygons, distance_threshold=15):
    filtered = []
    all_predicted = [poly for polys in predicted_polygons.values() for poly in polys]
    predicted_multipoly = MultiPolygon(all_predicted) if all_predicted else MultiPolygon()
    for orig_poly, type_id in original_polygons_with_type:
        orig_centroid = orig_poly.centroid
        keep = True
        for pred_poly in predicted_multipoly.geoms:
            pred_centroid = pred_poly.centroid
            if orig_centroid.distance(pred_centroid) < distance_threshold:
                keep = False
                break
        if keep:
            filtered.append((orig_poly, type_id))
    return filtered

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

def crop_image_by_scope(image_path, model_scope_str):
    if not model_scope_str:
        return image_path, None  # 如果没有范围，返回原始影像

    model_scope_polygons = parse_model_scope(model_scope_str)
    if not model_scope_polygons:
        return image_path, None  # 如果解析失败或为空，返回原始影像

    with rasterio.open(image_path) as src:
        out_image, out_transform = mask(src, model_scope_polygons, crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

        cropped_image_path = image_path.replace('.tif', '_cropped.tif')
        with rasterio.open(cropped_image_path, "w", **out_meta) as dest:
            dest.write(out_image)

    return cropped_image_path, out_transform

def filter_labels_by_scope(labels_data, model_scope_polygons):
    if not model_scope_polygons:
        return labels_data  # 如果没有范围，保留所有标注

    filtered_labels = []
    for label in labels_data:
        geom_str = label[1]  # 假设 geom_str 是坐标字符串
        coords_str_list = geom_str.split(',')
        coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
                       for i in range(0, len(coords_str_list), 2)]
        # 检查多边形的任意一点是否在模型作用范围内
        if any(any(Point(x, y).within(poly) for poly in model_scope_polygons) 
               for x, y in coords_list):
            filtered_labels.append(label)
    return filtered_labels

def parse_model_scope(model_scope_str):
    """解析 model_scope_str 为 Shapely 多边形列表"""
    try:
        model_scope = json.loads(model_scope_str)
        if not model_scope:
            return None
        polygons = []
        for scope_group in model_scope:
            for scope in scope_group:  # 处理嵌套结构
                coords = [(x, y) for x, y in scope]
                polygons.append(Polygon(coords))
        return polygons
    except json.JSONDecodeError as e:
        print(f"Error decoding model scope: {e}")
        return None

def crop_image_by_scope(image_path, model_scope_str):
    """根据模型范围裁剪影像"""
    if not model_scope_str:
        with rasterio.open(image_path) as src:
            original_transform = src.transform 
        return image_path, original_transform  # 如果没有范围，返回原始影像

    model_scope_polygons = parse_model_scope(model_scope_str)
    if not model_scope_polygons:
        with rasterio.open(image_path) as src:
            original_transform = src.transform 
        return image_path, original_transform  # 如果解析失败或为空，返回原始影像

    with rasterio.open(image_path) as src:
        out_image, out_transform = rasterio.mask.mask(src, model_scope_polygons, crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

        cropped_image_path = image_path.replace('.tif', '_cropped.tif')
        with rasterio.open(cropped_image_path, "w", **out_meta) as dest:
            dest.write(out_image)

    return cropped_image_path, out_transform
# SAM模型处理
# SAM_BOX
# Coordinate transformation setup
TRANSFORMER_3857_TO_4326 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
TRANSFORMER_4326_TO_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

def generate_bounding_boxes(labels_data, type_id):
    """Generate bounding boxes for polygons of a specific type_id, transforming to EPSG:4326."""
    boxes_3857 = []
    boxes_4326 = []
    for _, geom_str, tid, *_ in labels_data:
        if tid != type_id:
            continue
        try:
            coords_str_list = geom_str.split(',')
            coords_list = []
            for i in range(0, len(coords_str_list), 2):
                x = float(coords_str_list[i].strip())
                y = float(coords_str_list[i+1].strip())
                coords_list.append((x, y))
            polygon = Polygon(coords_list)
            minx, miny, maxx, maxy = polygon.bounds
            boxes_3857.append([minx, miny, maxx, maxy])  # Keep in EPSG:3857 for reference
            # Transform to EPSG:4326 for SAM prediction
            minx_4326, miny_4326 = TRANSFORMER_3857_TO_4326.transform(minx, miny)
            maxx_4326, maxy_4326 = TRANSFORMER_3857_TO_4326.transform(maxx, maxy)
            boxes_4326.append([minx_4326, miny_4326, maxx_4326, maxy_4326])  # Format: [left, bottom, right, top]
        except (ValueError, IndexError) as e:
            print(f"Error processing geometry string: {e}, geom_str: {geom_str}")
            continue
    return boxes_4326  # Return EPSG:4326 boxes for SAM

def identify_holes_and_split_SAM(mask, transform, type_id):
    """Convert mask to polygons, handling holes with connect_multiple_holes."""
    polygons = {}
    class_mask = mask.astype(np.uint8)
    contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or len(contours) == 0:
        return polygons

    class_polygons = []
    i = 0
    while i < len(contours):
        # if len(contours[i]) < 3 or cv2.contourArea(contours[i]) < min_area:
        #     i += 1
        #     continue
        if hierarchy[0][i][3] == -1:
            exterior_coords = [transform * (point[0][0], point[0][1]) for point in contours[i]]
            exterior_coords = [(x, y) for x, y in exterior_coords]
            interior_contours = []
            hole_idx = hierarchy[0][i][2]
            while hole_idx != -1:
                if len(contours[hole_idx]) >= 3:
                # if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
                    interior_coords = [transform * (point[0][0], point[0][1]) for point in contours[hole_idx]]
                    interior_coords = [(x, y) for x, y in interior_coords]
                    interior_contours.append(interior_coords)
                hole_idx = hierarchy[0][hole_idx][0]
            if interior_contours:
                final_coords = connect_multiple_holes(exterior_coords, interior_contours)
            else:
                final_coords = exterior_coords
            try:
                polygon = Polygon(final_coords)
                class_polygons.append(polygon)
            except Exception as e:
                print(f"创建多边形时出错: {e}")
        i += 1
    if class_polygons:
        polygons[type_id] = class_polygons
    return polygons

#   SAM
def crop_tiff_by_polygon(input_tiff_path, output_tiff_path, model_scope_str):
    """
    根据多边形范围裁剪TIFF影像
    
    参数:
    input_tiff_path: 输入TIFF文件路径
    output_tiff_path: 输出TIFF文件路径
    model_scope_str: JSON格式的多边形坐标字符串
    
    返回:
    bool: 裁剪成功返回True，否则返回False
    """
    try:
        # 解析多边形
        polygons = parse_model_scope(model_scope_str)
        if not polygons:
            print("No valid polygons found in the model scope.")
            return False
            
        # 将Shapely多边形转换为GeoJSON格式
        geoms = [mapping(polygon) for polygon in polygons]
            
        # 打开栅格数据
        with rasterio.open(input_tiff_path) as src:
            # 执行裁剪
            out_image, out_transform = mask(src, geoms, crop=True, all_touched=True)
            
            # 获取元数据
            out_meta = src.meta.copy()
            
            # 更新元数据
            out_meta.update({
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
            
            # 创建输出目录(如果不存在)
            output_dir = os.path.dirname(output_tiff_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # 保存裁剪后的栅格
            with rasterio.open(output_tiff_path, "w", **out_meta) as dest:
                dest.write(out_image)
                
            print(f"Successfully cropped image to {output_tiff_path}")
            return True
            
    except Exception as e:
        print(f"Error cropping TIFF: {e}")
        return False


def post_process_mask_sam(mask, min_object_size=10, hole_size_threshold=20, boundary_smoothing=3):
    """
    对输入的二值掩码进行后处理，包括移除小对象、填充小孔洞、平滑边界和众数滤波。
    
    参数：
        mask: 输入的二值掩码，numpy 数组，uint8 类型，0 为背景，1 为前景
        min_object_size: 最小对象面积阈值，小于此值的对象将被移除
        hole_size_threshold: 小孔洞面积阈值，小于此值的孔洞将被填充
        boundary_smoothing: 形态学平滑的核大小
        mode_filter_size: 众数滤波的窗口大小
    
    返回：
        processed_mask: 处理后的二值掩码，numpy 数组，uint8 类型
    """
    # 复制原始掩码
    original_mask = mask.copy().astype(np.uint8)
    
    # # 第一步：移除小对象
    # labeled_mask, num_features = scipy_label(original_mask)
    # if num_features > 0:
    #     properties = regionprops(labeled_mask)
    #     for prop in properties:
    #         if prop.area < min_object_size:
    #             labeled_mask[labeled_mask == prop.label] = 0
    # cleaned_mask = (labeled_mask > 0).astype(np.uint8)
    
    # # 第二步：填充小孔洞
    # filled_mask = cleaned_mask.copy()
    # contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # for contour in contours:
    #     temp_mask = np.zeros_like(cleaned_mask)
    #     cv2.drawContours(temp_mask, [contour], 0, 1, -1)
    #     temp_mask_inv = 1 - temp_mask
    #     holes, num_holes = scipy_label(temp_mask_inv)
    #     if num_holes > 0:
    #         hole_props = regionprops(holes)
    #         for hole in hole_props:
    #             if 0 < hole.area < hole_size_threshold:
    #                 filled_mask[holes == hole.label] = 1
    
    # # 第三步：形态学平滑
    # kernel = np.ones((boundary_smoothing, boundary_smoothing), np.uint8)
    # smoothed_mask = cv2.morphologyEx(filled_mask, cv2.MORPH_CLOSE, kernel)
    # smoothed_mask = cv2.morphologyEx(smoothed_mask, cv2.MORPH_OPEN, kernel)
    
    # # 第四步：众数滤波
    # def mode_function(window):
    #     values, counts = np.unique(window, return_counts=True)
    #     if len(counts) == 0:
    #         return 0  # 空窗口返回背景
    #     return values[np.argmax(counts)]
    
    # final_mask = generic_filter(
    #     smoothed_mask,
    #     mode_function,
    #     size=mode_filter_size,
    #     mode='nearest'
    # ).astype(np.uint8)
    
    # return final_mask
    labeled_mask, num_labels = label(original_mask, return_num=True)

    # 使用Numba移除小对象
    labeled_mask = remove_small_objects(labeled_mask, min_object_size)
    cleaned_mask = (labeled_mask > 0).astype(np.uint8)

    # 填充小孔
    filled_mask = cleaned_mask.copy()
    contours, hierarchy = cv2.findContours(cleaned_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    for i, contour in enumerate(contours):
        if hierarchy[0][i][3] != -1:  # 如果有父轮廓，说明是内部孔洞
            area = cv2.contourArea(contour)
            if 0 < area < hole_size_threshold:
                cv2.drawContours(filled_mask, [contour], 0, 1, -1)
    # filled_mask = cleaned_mask.copy()
    # contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # for contour in contours:
    #     temp_mask = np.zeros_like(cleaned_mask)
    #     cv2.drawContours(temp_mask, [contour], 0, 1, -1)
    #     temp_mask_inv = 1 - temp_mask
    #     holes = label(temp_mask_inv)
    #     hole_props = regionprops(holes)
    #     for hole in hole_props:
    #         if 0 < hole.area < hole_size_threshold:
    #             filled_mask[holes == hole.label] = 1

    # 形态学平滑
    # kernel = np.ones((boundary_smoothing, boundary_smoothing), np.uint8)
    # smoothed_mask = cv2.morphologyEx(filled_mask, cv2.MORPH_CLOSE, kernel)
    # smoothed_mask = cv2.morphologyEx(smoothed_mask, cv2.MORPH_OPEN, kernel)

    return filled_mask

def generate_point_coordinates_sam(labels_data, type_id):
    """Generate point coordinates for polygons of a specific type_id, transforming to EPSG:4326."""
    point_coords = []
    for _, geom_json, tid, *_ in labels_data:
        if tid != type_id:
            continue
        try:
            # Parse GeoJSON
            geom = json.loads(geom_json)
            if geom['type'] == 'Polygon':
                coords = geom['coordinates'][0]  # Get the first ring (exterior)
                for coord in coords:
                    x, y = coord
                    # Transform from EPSG:3857 to EPSG:4326
                    lon, lat = TRANSFORMER_3857_TO_4326.transform(x, y)
                    point_coords.append([lon, lat])
        except (ValueError, IndexError, KeyError) as e:
            print(f"Error processing geometry: {e}, geom_json: {geom_json}")
            continue
    return point_coords  # Return list of [lon, lat] pairs in EPSG:4326

# def generate_point_coordinates_sam(labels_data, type_id):
#     """
#     为特定 type_id 生成点坐标和多边形，将坐标从 EPSG:3857 转换为 EPSG:4326。
    
#     参数:
#         labels_data: 列表，元素为元组 (_, geom_str, tid, ...)，其中 geom_str 是逗号分隔的
#                      EPSG:3857 坐标字符串（如 'x1,y1' 或 'x1,y1,x2,y2,...,xn,yn'）。
#         type_id: 用于过滤几何对象的标识符。
    
#     返回:
#         元组: (point_coords, polygons)
#             - point_coords: 点坐标列表，格式为 [[lon, lat], ...]
#             - polygons: 字典 {type_id: [Polygon, ...]}，包含多边形对象
#     """
#     point_coords = []  # 存储点坐标
#     polygons_dict = {}  # 存储多边形结果
#     class_polygons = []  # 临时存储当前 type_id 的多边形

#     for _, geom_str, tid, *_ in labels_data:
#         if tid != type_id:  # 只处理匹配的 type_id
#             continue

#         try:
#             coords_str_list = geom_str.split(',')  # 分割坐标字符串
#             num_coords = len(coords_str_list)

#             if num_coords == 2:  # 处理点几何
#                 x = float(coords_str_list[0].strip())
#                 y = float(coords_str_list[1].strip())
#                 lon, lat = TRANSFORMER_3857_TO_4326.transform(x, y)
#                 point_coords.append([lon, lat])

#             else:  # 处理多边形几何（至少3个点）
#                 polygon_coords = []
#                 for i in range(0, num_coords, 2):
#                     x = float(coords_str_list[i].strip())
#                     y = float(coords_str_list[i + 1].strip())
#                     # lon, lat = TRANSFORMER_3857_TO_4326.transform(x, y)
#                     polygon_coords.append((lon, lat))

#                 # # 确保多边形闭合
#                 # if polygon_coords[0] != polygon_coords[-1]:
#                 #     polygon_coords.append(polygon_coords[0])

#                 # 创建多边形对象
#                 polygon = Polygon(polygon_coords)
#                 if polygon.is_valid:
#                     class_polygons.append(polygon)
#                 else:
#                     print(f"无效的多边形几何，来自: {geom_str}")

#         except (ValueError, IndexError) as e:
#             print(f"解析几何字符串时出错: {e}, geom_str: {geom_str}")
#             continue
#         except Exception as e:
#             print(f"创建多边形时出错: {e}, geom_str: {geom_str}")
#             continue

#     # 格式化多边形输出，与 identify_holes_and_split_SAM 一致
#     if class_polygons:
#         polygons_dict[type_id] = class_polygons

#     return point_coords, polygons_dict