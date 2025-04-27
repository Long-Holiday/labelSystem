# import rasterio
# import rasterio.windows
# import rasterio.features
# from shapely.geometry import Polygon
# import torch
# from torch.utils.data import Dataset
# import numpy as np
# import albumentations as A

# class RemoteSensingSegmentationDataset(Dataset):
#     def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index,
#                  background_class_index, apply_transforms=False):
#         self.image_path = image_path
#         self.labels_data = labels_data or []
#         self.num_classes = num_classes
#         self.type_id_to_class_index = type_id_to_class_index
#         self.background_class_index = background_class_index
#         self.apply_transforms = apply_transforms

#         # 获取图像全局信息
#         with rasterio.open(self.image_path) as src:
#             self.global_transform = src.transform
#             self.crs = src.crs
#             self.global_width = src.width
#             self.global_height = src.height
#             self.count = src.count

#         # 确定训练窗口
#         self.active_window = self._determine_training_window()
#         if not self.active_window:
#             raise ValueError("未能根据标签数据确定有效的训练窗口。")

#         # 加载窗口数据
#         self._load_image_data()
#         self._create_label_mask()

#         # 设置数据增强
#         if self.apply_transforms:
#             self.transforms = A.Compose([
#                 A.HorizontalFlip(p=0.5),
#                 A.VerticalFlip(p=0.5),
#                 A.RandomRotate90(p=0.5),
#                 A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.1, rotate_limit=45, p=0.5),
#                 A.RandomBrightnessContrast(p=0.5),
#             ])

#     def _determine_training_window(self):
#         """根据标注样本确定训练窗口，返回一个 Window 对象"""
#         if not self.labels_data:
#             print("没有标签数据，使用整个图像作为窗口。")
#             return rasterio.windows.Window(0, 0, self.global_width, self.global_height)

#         # 收集所有标注的地理坐标
#         all_coords = []
#         for _, geom_str, type_id, *_ in self.labels_data:
#             if type_id not in self.type_id_to_class_index:
#                 continue
#             try:
#                 coords_str_list = geom_str.split(',')
#                 coords = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
#                           for i in range(0, len(coords_str_list), 2)]
#                 all_coords.extend(coords)
#             except Exception as e:
#                 print(f"解析几何字符串时出错: {e}, geom_str: {geom_str}")
#                 continue

#         if not all_coords:
#             print("没有有效的标注坐标，使用整个图像作为窗口。")
#             return rasterio.windows.Window(0, 0, self.global_width, self.global_height)

#         # 计算最小外接矩形
#         minx = min(coord[0] for coord in all_coords)
#         miny = min(coord[1] for coord in all_coords)
#         maxx = max(coord[0] for coord in all_coords)
#         maxy = max(coord[1] for coord in all_coords)

#         # 添加边距（例如 50 像素）
#         padding = 50
#         window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, self.global_transform)
#         col_start = max(0, int(window.col_off) - padding)
#         row_start = max(0, int(window.row_off) - padding)
#         col_stop = min(self.global_width, int(window.col_off + window.width) + padding)
#         row_stop = min(self.global_height, int(window.row_off + window.height) + padding)
#         width = col_stop - col_start
#         height = row_stop - row_start

#         if width <= 0 or height <= 0:
#             raise ValueError(f"计算的训练窗口尺寸无效: width={width}, height={height}")

#         window = rasterio.windows.Window(col_start, row_start, width, height)
#         print(f"训练窗口: col_off={window.col_off}, row_off={window.row_off}, width={window.width}, height={window.height}")
#         return window

#     def _load_image_data(self):
#         """加载窗口内的图像数据"""
#         with rasterio.open(self.image_path) as src:
#             self.image = src.read(window=self.active_window)
#             self.window_transform = rasterio.windows.transform(self.active_window, src.transform)
#         self.image = self.image.astype(np.float32) / 255.0  # 标准化到 0-1

#     def _create_label_mask(self):
#         """创建窗口内的标签掩膜"""
#         width = self.active_window.width
#         height = self.active_window.height
#         self.label_mask = np.full((height, width), self.background_class_index, dtype=np.int64)
#         for _, geom_str, type_id, *_ in self.labels_data:
#             if type_id not in self.type_id_to_class_index:
#                 continue
#             class_index = self.type_id_to_class_index[type_id]
#             try:
#                 coords_str_list = geom_str.split(',')
#                 coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
#                                for i in range(0, len(coords_str_list), 2)]
#                 polygon = Polygon(coords_list)
#                 mask_temp = rasterio.features.rasterize(
#                     [(polygon, 1)],
#                     out_shape=(height, width),
#                     transform=self.window_transform,
#                     fill=0,
#                     all_touched=True,
#                     dtype=np.uint8
#                 )
#                 self.label_mask[mask_temp == 1] = class_index
#             except Exception as e:
#                 print(f"创建掩膜时出错: {e}, geom_str: {geom_str}")

#     def __len__(self):
#         return 1

#     def __getitem__(self, idx):
#         if idx != 0:
#             raise IndexError("此数据集只支持索引 0")
#         image_tensor = torch.from_numpy(self.image).float()
#         label_mask_tensor = torch.from_numpy(self.label_mask).long()
#         if self.transforms and self.apply_transforms:
#             image_np = image_tensor.permute(1, 2, 0).numpy()
#             label_mask_np = label_mask_tensor.numpy()
#             transformed = self.transforms(image=image_np, mask=label_mask_np)
#             image_tensor = torch.from_numpy(transformed['image']).permute(2, 0, 1).float()
#             label_mask_tensor = torch.from_numpy(transformed['mask']).long()
#         return image_tensor, label_mask_tensor, self.window_transform

# from matplotlib import patches, pyplot as plt
# import rasterio
# import rasterio.windows
# import rasterio.features
# from shapely.geometry import Polygon
# import torch
# from torch.utils.data import Dataset
# import numpy as np
# import albumentations as A

# class RemoteSensingSegmentationDataset(Dataset):
#     def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index,
#                  background_class_index, apply_transforms=False):
#         self.image_path = image_path
#         self.labels_data = labels_data or []
#         self.num_classes = num_classes
#         self.type_id_to_class_index = type_id_to_class_index
#         self.background_class_index = background_class_index
#         self.apply_transforms = apply_transforms

#         # 获取图像全局信息
#         with rasterio.open(self.image_path) as src:
#             self.global_transform = src.transform
#             self.crs = src.crs
#             self.global_width = src.width
#             self.global_height = src.height
#             self.count = src.count

#         # 确定多个训练窗口
#         self.windows = self._determine_training_windows()
#         print(f"训练窗口数量: {len(self.windows)}")

#         # 为每个窗口加载图像和掩膜
#         self.images = []
#         self.label_masks = []
#         self.window_transforms = []
#         for window in self.windows:
#             image, label_mask, window_transform = self._load_window_data(window)
#             self.images.append(image)
#             self.label_masks.append(label_mask)
#             self.window_transforms.append(window_transform)

#         # 设置数据增强
#         if self.apply_transforms:
#             self.transforms = A.Compose([
#                 A.HorizontalFlip(p=0.5),
#                 A.VerticalFlip(p=0.5),
#                 A.RandomRotate90(p=0.5),
#                 A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.1, rotate_limit=45, p=0.5),
#                 A.RandomBrightnessContrast(p=0.5),
#             ])

#     def _determine_training_windows(self):
#         """根据标注样本确定多个训练窗口，返回 Window 对象的列表"""
#         if not self.labels_data:
#             print("没有标签数据，使用整个图像作为单个窗口。")
#             return [rasterio.windows.Window(0, 0, self.global_width, self.global_height)]

#         # 收集所有标注的地理坐标
#         all_polygons = []
#         for _, geom_str, type_id, *_ in self.labels_data:
#             if type_id not in self.type_id_to_class_index:
#                 continue
#             try:
#                 coords_str_list = geom_str.split(',')
#                 coords = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
#                           for i in range(0, len(coords_str_list), 2)]
#                 polygon = Polygon(coords)
#                 all_polygons.append(polygon)
#             except Exception as e:
#                 print(f"解析几何字符串时出错: {e}, geom_str: {geom_str}")
#                 continue

#         if not all_polygons:
#             print("没有有效的标注多边形，使用整个图像作为单个窗口。")
#             return [rasterio.windows.Window(0, 0, self.global_width, self.global_height)]

#         # 分组相近的多边形
#         groups = []
#         processed = set()
#         for i, poly1 in enumerate(all_polygons):
#             if i in processed:
#                 continue
#             group = [poly1]
#             processed.add(i)
#             for j, poly2 in enumerate(all_polygons):
#                 if j not in processed and poly1.distance(poly2) < 0.001:  # 调整阈值
#                     group.append(poly2)
#                     processed.add(j)
#             groups.append(group)

#         # 为每个组计算窗口
#         windows = []
#         padding = 5  # 像素边距
#         for group in groups:
#             minx = min(poly.bounds[0] for poly in group)
#             miny = min(poly.bounds[1] for poly in group)
#             maxx = max(poly.bounds[2] for poly in group)
#             maxy = max(poly.bounds[3] for poly in group)
#             window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, self.global_transform)
#             col_start = max(0, int(window.col_off) - padding)
#             row_start = max(0, int(window.row_off) - padding)
#             col_stop = min(self.global_width, int(window.col_off + window.width) + padding)
#             row_stop = min(self.global_height, int(window.row_off + window.height) + padding)
#             width = col_stop - col_start
#             height = row_stop - row_start
#             if width > 0 and height > 0:
#                 windows.append(rasterio.windows.Window(col_start, row_start, width, height))
#             else:
#                 print(f"跳过无效窗口: width={width}, height={height}")

#         if not windows:
#             print("未找到有效窗口，使用整个图像作为单个窗口。")
#             return [rasterio.windows.Window(0, 0, self.global_width, self.global_height)]

#         return windows

#     def _load_window_data(self, window):
#         """加载指定窗口的图像、掩膜和变换矩阵"""
#         with rasterio.open(self.image_path) as src:
#             image = src.read(window=window)
#             window_transform = rasterio.windows.transform(window, src.transform)
#         image = image.astype(np.float32) / 255.0

#         width = window.width
#         height = window.height
#         label_mask = np.full((height, width), self.background_class_index, dtype=np.int64)
#         for _, geom_str, type_id, *_ in self.labels_data:
#             if type_id not in self.type_id_to_class_index:
#                 continue
#             class_index = self.type_id_to_class_index[type_id]
#             try:
#                 coords_str_list = geom_str.split(',')
#                 coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
#                                for i in range(0, len(coords_str_list), 2)]
#                 polygon = Polygon(coords_list)
#                 mask_temp = rasterio.features.rasterize(
#                     [(polygon, 1)],
#                     out_shape=(height, width),
#                     transform=window_transform,
#                     fill=0,
#                     all_touched=True,
#                     dtype=np.uint8
#                 )
#                 label_mask[mask_temp == 1] = class_index
#             except Exception as e:
#                 print(f"创建掩膜时出错: {e}, geom_str: {geom_str}")
#         return image, label_mask, window_transform

#     def __len__(self):
#         return len(self.windows)

#     def __getitem__(self, idx):
#         image = self.images[idx]
#         label_mask = self.label_masks[idx]
#         window_transform = self.window_transforms[idx]

#         image_tensor = torch.from_numpy(image).float()
#         label_mask_tensor = torch.from_numpy(label_mask).long()

#         if self.transforms and self.apply_transforms:
#             image_np = image_tensor.permute(1, 2, 0).numpy()
#             label_mask_np = label_mask_tensor.numpy()
#             transformed = self.transforms(image=image_np, mask=label_mask_np)
#             image_tensor = torch.from_numpy(transformed['image']).permute(2, 0, 1).float()
#             label_mask_tensor = torch.from_numpy(transformed['mask']).long()

#         return image_tensor, label_mask_tensor, window_transform

import rasterio
import rasterio.windows
import rasterio.features
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import torch
from torch.utils.data import Dataset
import numpy as np
import albumentations as A
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class RemoteSensingSegmentationDataset(Dataset):
    def __init__(self, image_path, labels_data, num_classes, type_id_to_class_index,
                 background_class_index, apply_transforms=False, vis_output_path="./visualization.png",
                 target_size=(512, 512)):
        self.image_path = image_path
        self.labels_data = labels_data or []
        self.num_classes = num_classes
        self.type_id_to_class_index = type_id_to_class_index
        self.background_class_index = background_class_index
        self.apply_transforms = apply_transforms
        self.vis_output_path = vis_output_path
        self.target_size = target_size

        # 获取图像全局信息
        with rasterio.open(self.image_path) as src:
            self.global_transform = src.transform
            self.crs = src.crs
            self.global_width = src.width
            self.global_height = src.height
            self.count = src.count

        # 确定多个训练窗口
        self.windows = self._determine_training_windows()

        # 为每个窗口加载图像和掩膜
        self.images = []
        self.label_masks = []
        self.window_transforms = []
        for window in self.windows:
            image, label_mask, window_transform = self._load_window_data(window)
            self.images.append(image)
            self.label_masks.append(label_mask)
            self.window_transforms.append(window_transform)

        # 可视化窗口、样本和影像的位置关系
        self._visualize_windows_and_samples()

        # 设置数据增强
        if self.apply_transforms:
            self.transforms = A.Compose([
                A.Resize(height=target_size[0], width=target_size[1], always_apply=True),
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.5),
                A.RandomRotate90(p=0.5),
                A.ShiftScaleRotate(shift_limit=0.0625, scale_limit=0.1, rotate_limit=45, p=0.5),
                A.RandomBrightnessContrast(p=0.5),
            ])
        else:
            self.transforms = A.Compose([
                A.Resize(height=target_size[0], width=target_size[1], always_apply=True),
            ])

    def _determine_training_windows(self):
        """根据标注样本确定多个训练窗口，返回 Window 对象的列表"""
        if not self.labels_data:
            print("没有标签数据，使用整个图像作为单个窗口。")
            return [rasterio.windows.Window(0, 0, self.global_width, self.global_height)]

        # 收集所有标注的地理坐标
        all_polygons = []
        for _, geom_str, type_id, *_ in self.labels_data:
            if type_id not in self.type_id_to_class_index:
                continue
            try:
                coords_str_list = geom_str.split(',')
                coords = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
                          for i in range(0, len(coords_str_list), 2)]
                polygon = Polygon(coords)
                all_polygons.append(polygon)
            except Exception as e:
                print(f"解析几何字符串时出错: {e}, geom_str: {geom_str}")
                continue

        if not all_polygons:
            print("没有有效的标注多边形，使用整个图像作为单个窗口。")
            return [rasterio.windows.Window(0, 0, self.global_width, self.global_height)]

        # 生成每个多边形的边界框
        bounding_boxes = [box(*poly.bounds) for poly in all_polygons]

        # 迭代合并重叠的边界框，直到没有重叠
        while True:
            merged_boxes = []
            merged = False
            i = 0
            while i < len(bounding_boxes):
                current_box = bounding_boxes[i]
                overlapping = [current_box]
                j = i + 1
                while j < len(bounding_boxes):
                    if current_box.intersects(bounding_boxes[j]):
                        overlapping.append(bounding_boxes[j])
                        bounding_boxes.pop(j)
                        merged = True
                    else:
                        j += 1
                if len(overlapping) > 1:
                    merged_poly = unary_union(overlapping)
                    merged_boxes.append(box(*merged_poly.bounds))
                else:
                    merged_boxes.append(current_box)
                bounding_boxes.pop(i)
            bounding_boxes = merged_boxes
            if not merged:
                break  # 没有新的合并，退出循环

        # 为每个合并后的边界框创建窗口
        windows = []
        padding = 50  # 像素边距
        for merged_box in bounding_boxes:
            minx, miny, maxx, maxy = merged_box.bounds
            window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, self.global_transform)
            col_start = max(0, int(window.col_off) - padding)
            row_start = max(0, int(window.row_off) - padding)
            col_stop = min(self.global_width, int(window.col_off + window.width) + padding)
            row_stop = min(self.global_height, int(window.row_off + window.height) + padding)
            width = col_stop - col_start
            height = row_stop - row_start
            if width > 0 and height > 0:
                windows.append(rasterio.windows.Window(col_start, row_start, width, height))
            else:
                print(f"跳过无效窗口: width={width}, height={height}")

        if not windows:
            print("未找到有效窗口，使用整个图像作为单个窗口。")
            return [rasterio.windows.Window(0, 0, self.global_width, self.global_height)]

        return windows

    def _load_window_data(self, window):
        """加载指定窗口的图像、掩膜和变换矩阵"""
        with rasterio.open(self.image_path) as src:
            image = src.read(window=window)
            window_transform = rasterio.windows.transform(window, src.transform)
        image = image.astype(np.float32) / 255.0

        width = window.width
        height = window.height
        label_mask = np.full((height, width), self.background_class_index, dtype=np.int64)
        for _, geom_str, type_id, *_ in self.labels_data:
            if type_id not in self.type_id_to_class_index:
                continue
            class_index = self.type_id_to_class_index[type_id]
            try:
                coords_str_list = geom_str.split(',')
                coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
                               for i in range(0, len(coords_str_list), 2)]
                polygon = Polygon(coords_list)
                mask_temp = rasterio.features.rasterize(
                    [(polygon, 1)],
                    out_shape=(height, width),
                    transform=window_transform,
                    fill=0,
                    all_touched=True,
                    dtype=np.uint8
                )
                label_mask[mask_temp == 1] = class_index
            except Exception as e:
                print(f"创建掩膜时出错: {e}, geom_str: {geom_str}")
        return image, label_mask, window_transform

    def _visualize_windows_and_samples(self):
        """可视化影像、窗口和样本的位置关系，并保存结果"""
        with rasterio.open(self.image_path) as src:
            scale_factor = 0.1
            window = rasterio.windows.Window(0, 0, self.global_width, self.global_height)
            image = src.read(
                out_shape=(
                    src.count,
                    int(self.global_height * scale_factor),
                    int(self.global_width * scale_factor)
                ),
                resampling=rasterio.enums.Resampling.bilinear
            )
            transform = src.transform * src.transform.scale(
                (self.global_width / image.shape[2]),
                (self.global_height / image.shape[1])
            )

        fig, ax = plt.subplots(figsize=(12, 12))
        if image.shape[0] >= 3:
            rgb_image = image[:3].transpose(1, 2, 0)
        else:
            rgb_image = np.stack([image[0]] * 3, axis=2)
        ax.imshow(rgb_image)

        for i, window in enumerate(self.windows):
            col_start = window.col_off * scale_factor
            row_start = window.row_off * scale_factor
            width = window.width * scale_factor
            height = window.height * scale_factor
            rect = patches.Rectangle(
                (col_start, row_start), width, height,
                linewidth=2, edgecolor='yellow', facecolor='none', label=f'Window {i+1}' if i == 0 else None
            )
            ax.add_patch(rect)

        for _, geom_str, type_id, *_ in self.labels_data:
            if type_id not in self.type_id_to_class_index:
                continue
            try:
                coords_str_list = geom_str.split(',')
                coords = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip()))
                          for i in range(0, len(coords_str_list), 2)]
                polygon = Polygon(coords)
                pixel_coords = [
                    rasterio.transform.rowcol(transform, x, y)
                    for x, y in polygon.exterior.coords
                ]
                pixel_coords = [(col * scale_factor, row * scale_factor) for row, col in pixel_coords]
                poly_patch = patches.Polygon(
                    pixel_coords, closed=True, edgecolor='red', facecolor='none', linewidth=1.5,
                    label='Sample' if _ == self.labels_data[0][0] else None
                )
                ax.add_patch(poly_patch)
            except Exception as e:
                print(f"可视化多边形时出错: {e}, geom_str: {geom_str}")

        ax.set_title("Image with Windows and Samples")
        ax.legend()
        ax.set_xlabel("Column (pixels)")
        ax.set_ylabel("Row (pixels)")
        plt.savefig(self.vis_output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"可视化结果已保存至: {self.vis_output_path}")

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        image = self.images[idx]
        label_mask = self.label_masks[idx]
        window_transform = self.window_transforms[idx]

        image_tensor = torch.from_numpy(image).float()
        label_mask_tensor = torch.from_numpy(label_mask).long()

        image_np = image_tensor.permute(1, 2, 0).numpy()
        label_mask_np = label_mask_tensor.numpy()
        transformed = self.transforms(image=image_np, mask=label_mask_np)
        image_tensor = torch.from_numpy(transformed['image']).permute(2, 0, 1).float()
        label_mask_tensor = torch.from_numpy(transformed['mask']).long()

        return image_tensor, label_mask_tensor, window_transform