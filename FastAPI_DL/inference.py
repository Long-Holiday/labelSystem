import json
import sys
import os
import rasterio
from shapely import MultiPolygon, Polygon
import torch
from torch.utils.data import DataLoader
from models.light_unet import LightUNet
from models.unet import UNet
from models.fast_scnn import FastSCNN
from models.xgboostt import XGBoost
from dataset import RemoteSensingSegmentationDataset
from utils import (
    connect_db, crop_image_by_scope, fetch_labels_from_db, delete_existing_results_db,
    insert_segmentation_results_db,
    post_process_mask, identify_holes_and_split,
    process_yolo_results, draw_boxes_on_image,
    fetch_map_server_from_db, fetch_typeid_from_db, create_original_label_mask,fetch_model_from_db
)
import joblib
import numpy as np
from PIL import Image

def predict_torch_model(model, image_tensor, device):
    """使用 PyTorch 模型进行预测"""
    model.eval()
    with torch.no_grad():
        image_tensor = image_tensor.unsqueeze(0).to(device)
        outputs = model(image_tensor)
        if outputs.shape[2:] != image_tensor.shape[2:]:
            outputs = torch.nn.functional.interpolate(outputs, size=image_tensor.shape[2:], mode='bilinear',
                                                      align_corners=False)
        probabilities = torch.softmax(outputs, dim=1)
        predicted_mask = torch.argmax(probabilities, dim=1).squeeze().cpu().numpy()
    return predicted_mask.astype(np.uint8)

def predict_sklearn_model(model, X, image_shape):
    """使用 scikit-learn 模型进行预测"""
    predictions = model.predict(X)
    return predictions.reshape(image_shape[1], image_shape[2]).astype(np.uint8)

def predict_large_image_with_overlap(model, image, block_size, overlap, predict_func, device=None):
    C, H, W = image.shape
    block_h, block_w = block_size
    overlap_h, overlap_w = overlap
    step_h = block_h - overlap_h
    step_w = block_w - overlap_w

    pad_h = (step_h - H % step_h) % step_h
    pad_w = (step_w - W % step_w) % step_w
    padded_image = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode='constant')
    padded_H, padded_W = padded_image.shape[1], padded_image.shape[2]

    predicted_mask = np.zeros((padded_H, padded_W), dtype=np.float32)
    count_mask = np.zeros((padded_H, padded_W), dtype=np.float32)

    for i in range(0, padded_H - overlap_h, step_h):
        for j in range(0, padded_W - overlap_w, step_w):
            block = padded_image[:, i:i + block_h, j:j + block_w]
            if predict_func.__name__ == "predict_torch_model":
                block_tensor = torch.from_numpy(block).float().to(device)
                block_pred = predict_func(model, block_tensor, device)
            else:  # predict_sklearn_model
                X_block = block.transpose(1, 2, 0).reshape(-1, block.shape[0])
                block_pred = predict_func(model, X_block, (None, block_h, block_w))
            predicted_mask[i:i + block_h, j:j + block_w] += block_pred
            count_mask[i:i + block_h, j:j + block_w] += 1

    predicted_mask /= count_mask
    predicted_mask = np.round(predicted_mask).astype(np.uint8)
    return predicted_mask[:H, :W]

def inference(argv=None):
    TASK_ID = int(argv[1])
    MAPFILE_PATH = argv[2]
    USER_ID = int(argv[3])
    MODEL_name = str(argv[4]).split(".")[0]
    model_scope_str = argv[9]  # 模型作用范围

    # 类别映射
    class_mapping = argv[10]

    # 解析 model_scope
    try:
        model_scope = json.loads(model_scope_str)
        if not model_scope:
            print("No model scope provided, will process entire image.")
        else:
            print("Model scope coordinates:", model_scope)
    except json.JSONDecodeError as e:
        print(f"Error decoding model scope: {e}")
        model_scope_str = None

    # 连接数据库
    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return

    model_inf = fetch_model_from_db(conn,MODEL_name)

    # 获取地图服务器路径
    map_servers = fetch_map_server_from_db(conn, TASK_ID)
    if not map_servers:
        print(f"task_id {TASK_ID} 未找到地图服务器路径，请检查数据库。")
        conn.close()
        return
    map_name = map_servers[0][0]
    IMAGE_PATH = os.path.join(MAPFILE_PATH, f"{map_name}.tif")

    # 获取标签数据
    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        print(f"task_id {TASK_ID} 没有找到标签数据，将不使用原始标签掩膜。")
        labels_data = None

    # 提取 user_id 和 status
    user_id = USER_ID
    status = 0
    # type_arr = fetch_typeid_from_db(conn, TASK_ID)

    # 定义模型保存路径
    model_save_path = model_inf['path']

    # 设置设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_status = model_inf["status"]

    if model_status == 0:

        MODEL_TYPE = model_inf['model_type']

        # 解析 class_mapping
        try:
            # 如果 class_mapping 已经是字典，直接使用；否则尝试解析为字典
            class_mapping_dict = class_mapping if isinstance(class_mapping, dict) else json.loads(class_mapping)
        except json.JSONDecodeError as e:
            print(f"Error decoding class_mapping: {e}")
            conn.close()
            return

        # 根据模型类型设置类别映射
        if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
            num_classes = len(class_mapping_dict) + 1  # 假设有一个背景类
            class_index_to_type_id = {}
            background_class_index = None
            for idx in range(num_classes):
                if idx in class_mapping_dict and class_mapping_dict[idx]:
                    class_index_to_type_id[idx] = class_mapping_dict[idx]
                else:
                    background_class_index = idx
            if background_class_index is None:
                print("No background class found in class_mapping.")
                conn.close()
                return
        elif MODEL_TYPE == "yolo":
            class_id_to_type_id = {k: v for k, v in class_mapping_dict.items() if v}  # 仅保留非空映射

        # 根据模型类型加载模型
        if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
            with rasterio.open(IMAGE_PATH) as src:
                in_channels = src.count
            # num_classes = len(type_arr[0][0].split(",")) + 1
            num_classes = model_inf["output_num"]
            if MODEL_TYPE == "light_unet":
                model = LightUNet(in_channels=in_channels, num_classes=num_classes).to(device)
            elif MODEL_TYPE == "unet":
                model = UNet(in_channels=in_channels, num_classes=num_classes).to(device)
            elif MODEL_TYPE == "fast_scnn":
                model = FastSCNN(in_channels=in_channels, num_classes=num_classes).to(device)
            model.load_state_dict(torch.load(model_save_path, map_location=device))
        elif MODEL_TYPE == "xgboost":
            model = joblib.load(model_save_path)
        elif MODEL_TYPE == "yolo":
            from ultralytics import YOLO
            model = YOLO(model_save_path)
        else:
            print(f"未知的模型类型: {MODEL_TYPE}")
            conn.close()
            return

        # 进行推理
        if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
            # 直接加载整个图像
            with rasterio.open(IMAGE_PATH) as src:
                image = src.read().astype(np.float32) / 255.0  # (C, H, W)
                window_transform = src.transform  # 用于后续多边形转换

            block_size = (1024, 1024)
            overlap = (128, 128)
            _, H, W = image.shape

            if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
                if H <= block_size[0] and W <= block_size[1]:
                    image_tensor = torch.from_numpy(image).float().to(device)
                    predicted_mask = predict_torch_model(model, image_tensor, device)
                else:
                    predicted_mask = predict_large_image_with_overlap(
                        model, image, block_size, overlap, predict_torch_model, device)

            # 后处理掩膜
            predicted_mask = post_process_mask(
                predicted_mask, min_object_size=int(argv[5]), hole_size_threshold=int(argv[6]),
                boundary_smoothing=int(argv[7])
            )

            # 转换为多边形
            segmentation_polygons = identify_holes_and_split(
                predicted_mask, window_transform,
                class_index_to_type_id,
                background_class_index
            )

            # 更新数据库结果
            insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)
            torch.cuda.empty_cache()

        elif MODEL_TYPE == "yolo":
            temp_dir = "temp_inference"
            os.makedirs(temp_dir, exist_ok=True)
            jpeg_filename = f"inference_{TASK_ID}.jpg"
            jpeg_path = os.path.join(temp_dir, jpeg_filename)

            cropped_image_path, crop_transform = crop_image_by_scope(IMAGE_PATH, model_scope_str)

            with rasterio.open(cropped_image_path) as src:
                image = src.read()
                image = image.transpose(1, 2, 0)
                if image.shape[2] > 3:
                    image = image[:, :, :3]
                image = (image / image.max() * 255).astype(np.uint8)
                Image.fromarray(image).save(jpeg_path, "JPEG")

            results = model(jpeg_path, conf=float(argv[5]), imgsz=int(argv[6]))

            detection_polygons, _, _ = process_yolo_results(
                results, crop_transform, TASK_ID, user_id, status, conn,
                class_id_to_type_id, None, cropped_image_path
            )

            original_polygons_with_type = []
            if labels_data:
                for _, geom_str, type_id, *_ in labels_data:
                    coords_str_list = geom_str.split(',')
                    coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i + 1].strip()))
                                for i in range(0, len(coords_str_list), 2)]
                    poly = Polygon(coords_list)
                    original_polygons_with_type.append((poly, type_id))

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

            filtered_original_with_type = filter_original_labels(original_polygons_with_type, detection_polygons,
                                                                distance_threshold=float(argv[7]))
            
            print("q")

            filtered_original_dict = {}
            for poly, type_id in filtered_original_with_type:
                if type_id not in filtered_original_dict:
                    filtered_original_dict[type_id] = []
                filtered_original_dict[type_id].append(poly)

            type_ids = set(detection_polygons.keys()) | set(filtered_original_dict.keys())
            segmentation_polygons = {type_id: filtered_original_dict.get(type_id, []) + detection_polygons.get(type_id, [])
                                    for type_id in type_ids}

            delete_existing_results_db(conn, TASK_ID)
            insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

            if model_scope:
                os.remove(jpeg_path)
    
            torch.cuda.empty_cache()
    else:
        # 加载TorchScript模型
        try:
            print("使用torchscript模型进行推理")
            print(f"加载模型: {model_save_path}")
            model = torch.jit.load(model_save_path).to(device)
            model.eval()
            
            # 使用相同的class_mapping解析逻辑
            try:
                class_mapping_dict = class_mapping if isinstance(class_mapping, dict) else json.loads(class_mapping)
                num_classes = len(class_mapping_dict) + 1
                class_index_to_type_id = {}
                background_class_index = None
                for idx in range(num_classes):
                    if idx in class_mapping_dict and class_mapping_dict[idx]:
                        class_index_to_type_id[idx] = class_mapping_dict[idx]
                    else:
                        background_class_index = idx
                if background_class_index is None:
                    print("No background class found in class_mapping.")
                    conn.close()
                    return
            except Exception as e:
                print(f"类别映射解析失败: {e}")
                conn.close()
                return
        
            # 图像加载和预处理
            with rasterio.open(IMAGE_PATH) as src:
                image = src.read().astype(np.float32) / 255.0
                window_transform = src.transform
            
            # 分块推理
            block_size = (1024, 1024)
            overlap = (128, 128)
            _, H, W = image.shape
            
            if H <= block_size[0] and W <= block_size[1]:
                image_tensor = torch.from_numpy(image).float().to(device)
                with torch.no_grad():
                    outputs = model(image_tensor.unsqueeze(0))
                predicted_mask = torch.argmax(torch.softmax(outputs, dim=1), dim=1).squeeze().cpu().numpy()
            else:
                def torchscript_predict(model, block_tensor, device):
                    with torch.no_grad():
                        outputs = model(block_tensor.unsqueeze(0))
                    return torch.argmax(torch.softmax(outputs, dim=1), dim=1).squeeze().cpu().numpy()
                
                predicted_mask = predict_large_image_with_overlap(
                    model, image, block_size, overlap, torchscript_predict, device
                )
            
            # 后续处理与现有流程一致
            predicted_mask = post_process_mask(
                predicted_mask, min_object_size=int(argv[5]), hole_size_threshold=int(argv[6]),
                boundary_smoothing=int(argv[7])
            )
            segmentation_polygons = identify_holes_and_split(
                predicted_mask, window_transform,
                class_index_to_type_id,
                background_class_index
            )
            insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)
            torch.cuda.empty_cache()
        except Exception as e:
            print(f"TorchScript模型加载或推理失败: {e}")
            conn.close()
            return

    conn.close()
    print("推理任务完成!")
# import json
# import sys
# import os
# import rasterio
# from shapely import MultiPolygon, Polygon
# import torch
# from torch.utils.data import DataLoader
# from models.light_unet import LightUNet
# from models.unet import UNet
# from models.fast_scnn import FastSCNN
# from models.xgboostt import XGBoost
# from dataset import RemoteSensingSegmentationDataset
# from utils import (
#     connect_db, crop_image_by_scope, fetch_labels_from_db, delete_existing_results_db,
#     insert_segmentation_results_db,
#     post_process_mask, identify_holes_and_split,
#     process_yolo_results, draw_boxes_on_image,
#     fetch_map_server_from_db, fetch_typeid_from_db, create_original_label_mask,fetch_model_from_db
# )
# import joblib
# import numpy as np
# from PIL import Image


# def predict_torch_model(model, image_tensor, device):
#     """使用 PyTorch 模型进行预测"""
#     model.eval()
#     with torch.no_grad():
#         image_tensor = image_tensor.unsqueeze(0).to(device)
#         outputs = model(image_tensor)
#         if outputs.shape[2:] != image_tensor.shape[2:]:
#             outputs = torch.nn.functional.interpolate(outputs, size=image_tensor.shape[2:], mode='bilinear',
#                                                       align_corners=False)
#         probabilities = torch.softmax(outputs, dim=1)
#         predicted_mask = torch.argmax(probabilities, dim=1).squeeze().cpu().numpy()
#     return predicted_mask.astype(np.uint8)


# def predict_sklearn_model(model, X, image_shape):
#     """使用 scikit-learn 模型进行预测"""
#     predictions = model.predict(X)
#     return predictions.reshape(image_shape[1], image_shape[2]).astype(np.uint8)


# # def predict_large_image(model, image, block_size, predict_func, device=None):
# #     """
# #     对大型图像进行分块推理

# #     参数:
# #         model: 加载的模型
# #         image: 输入图像，形状为 (C, H, W)
# #         block_size: 分块大小，例如 (1024, 1024)
# #         predict_func: 预测函数（predict_torch_model 或 predict_sklearn_model）
# #         device: PyTorch 设备（对于 PyTorch 模型）

# #     返回:
# #         predicted_mask: 完整图像的预测掩膜
# #     """
# #     C, H, W = image.shape
# #     block_h, block_w = block_size

# #     # 计算填充大小，使图像尺寸能被块大小整除
# #     pad_h = (block_h - H % block_h) % block_h
# #     pad_w = (block_w - W % block_w) % block_w

# #     # 填充图像
# #     padded_image = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode='constant')
# #     padded_C, padded_H, padded_W = padded_image.shape

# #     # 初始化完整掩膜
# #     predicted_mask = np.zeros((padded_H, padded_W), dtype=np.uint8)

# #     # 分块预测
# #     for i in range(0, padded_H, block_h):
# #         for j in range(0, padded_W, block_w):
# #             block = padded_image[:, i:i + block_h, j:j + block_w]
# #             if device:  # PyTorch 模型
# #                 block_tensor = torch.from_numpy(block).float().to(device)
# #                 block_pred = predict_func(model, block_tensor, device)
# #             else:  # scikit-learn 模型
# #                 X_block = block.transpose(1, 2, 0).reshape(-1, block.shape[0])
# #                 block_pred = predict_func(model, X_block, (None, block_h, block_w))
# #             predicted_mask[i:i + block_h, j:j + block_w] = block_pred

# #     # 裁剪回原始图像大小
# #     predicted_mask = predicted_mask[:H, :W]
# #     return predicted_mask



# def predict_large_image_with_overlap(model, image, block_size, overlap, predict_func, device=None):
#     C, H, W = image.shape
#     block_h, block_w = block_size
#     overlap_h, overlap_w = overlap
#     step_h = block_h - overlap_h
#     step_w = block_w - overlap_w

#     pad_h = (step_h - H % step_h) % step_h
#     pad_w = (step_w - W % step_w) % step_w
#     padded_image = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode='constant')
#     padded_H, padded_W = padded_image.shape[1], padded_image.shape[2]

#     predicted_mask = np.zeros((padded_H, padded_W), dtype=np.float32)
#     count_mask = np.zeros((padded_H, padded_W), dtype=np.float32)

#     for i in range(0, padded_H - overlap_h, step_h):
#         for j in range(0, padded_W - overlap_w, step_w):
#             block = padded_image[:, i:i + block_h, j:j + block_w]
#             if predict_func.__name__ == "predict_torch_model":
#                 block_tensor = torch.from_numpy(block).float().to(device)
#                 block_pred = predict_func(model, block_tensor, device)
#             else:  # predict_sklearn_model
#                 X_block = block.transpose(1, 2, 0).reshape(-1, block.shape[0])
#                 block_pred = predict_func(model, X_block, (None, block_h, block_w))
#             predicted_mask[i:i + block_h, j:j + block_w] += block_pred
#             count_mask[i:i + block_h, j:j + block_w] += 1

#     predicted_mask /= count_mask
#     predicted_mask = np.round(predicted_mask).astype(np.uint8)
#     return predicted_mask[:H, :W]


# # 如果你的 XGBoost 模型是在 xgboostt.py 中定义的类
# # 确保 model.predict(X) 能被正确调用并返回预测结果
# # from models.xgboostt import XGBoost # 假设你的模型类在这里

# # def predict_large_image_sklearn_with_overlap(model, image, block_size, overlap):
# #     """
# #     对大型图像使用 scikit-learn 模型（如 XGBoost）进行带重叠的分块推理。

# #     参数:
# #         model: 加载的 scikit-learn 模型（需要实现 predict 方法）。
# #                例如，可以是训练好的 XGBoost 模型对象。
# #         image: 输入图像，形状为 (C, H, W) 的 NumPy 数组。 C=通道数, H=高度, W=宽度。
# #         block_size: 分块大小 (block_h, block_w)，例如 (1024, 1024)。
# #         overlap: 重叠大小 (overlap_h, overlap_w)，例如 (128, 128)。

# #     返回:
# #         predicted_mask: 完整图像的预测掩膜 (H, W)，uint8 类型。
# #     """
# #     C, H, W = image.shape
# #     block_h, block_w = block_size
# #     overlap_h, overlap_w = overlap

# #     # 确保 overlap 不大于 block_size 且非负
# #     overlap_h = min(max(0, overlap_h), block_h - 1)
# #     overlap_w = min(max(0, overlap_w), block_w - 1)

# #     step_h = block_h - overlap_h
# #     step_w = block_w - overlap_w

# #     # --- 更鲁棒的填充计算 ---
# #     # 计算需要多少步才能覆盖整个维度
# #     steps_h = math.ceil(max(0, H - overlap_h) / step_h) if H > overlap_h else 1
# #     steps_w = math.ceil(max(0, W - overlap_w) / step_w) if W > overlap_w else 1

# #     # 计算填充后的总高度和宽度
# #     padded_H = overlap_h + steps_h * step_h
# #     padded_W = overlap_w + steps_w * step_w

# #     # 计算需要填充的大小
# #     pad_h = padded_H - H
# #     pad_w = padded_W - W
# #     # --- 结束填充计算 ---

# #     # 填充图像
# #     # 使用 'reflect' 或 'symmetric' 可能比 'constant' 在边缘效果更好
# #     padded_image = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode='reflect')

# #     # 初始化预测掩膜（用于累加）和计数掩膜
# #     predicted_mask_sum = np.zeros((padded_H, padded_W), dtype=np.float32)
# #     count_mask = np.zeros((padded_H, padded_W), dtype=np.float32)

# #     print(f"原始图像: {H}x{W}, 填充后图像: {padded_H}x{padded_W}")
# #     print(f"块大小: {block_h}x{block_w}, 重叠: {overlap_h}x{overlap_w}, 步长: {step_h}x{step_w}")

# #     # 分块预测
# #     for i in range(0, padded_H - overlap_h, step_h):
# #         # 当前块的实际行范围
# #         row_start = i
# #         row_end = min(i + block_h, padded_H)
# #         for j in range(0, padded_W - overlap_w, step_w):
# #             # 当前块的实际列范围
# #             col_start = j
# #             col_end = min(j + block_w, padded_W)

# #             # 提取当前块 (注意：这里的 i, j 是起始点)
# #             block = padded_image[:, row_start:row_end, col_start:col_end]
# #             current_C, current_h, current_w = block.shape

# #             # 检查块大小是否有效
# #             if current_h == 0 or current_w == 0:
# #                 print(f"跳过空块，位置 ({row_start},{col_start}), 尺寸 {current_h}x{current_w}")
# #                 continue

# #             # 准备 scikit-learn 输入格式 (N_pixels, N_features)
# #             # N_pixels = current_h * current_w
# #             # N_features = current_C
# #             X_block = block.transpose(1, 2, 0).reshape(-1, current_C)

# #             # 执行预测
# #             # model.predict 应该返回一个一维数组，长度为 current_h * current_w
# #             try:
# #                 block_pred_flat = model.predict(X_block)
# #             except Exception as e:
# #                 print(f"模型预测出错，块位置 ({row_start},{col_start}), 尺寸 {current_h}x{current_w}: {e}")
# #                 continue # 跳过这个块

# #             # 检查预测结果的元素数量是否正确
# #             expected_pixels = current_h * current_w
# #             if block_pred_flat.shape[0] != expected_pixels:
# #                print(f"形状不匹配! 预测得到 {block_pred_flat.shape[0]} 个像素, "
# #                      f"期望 {expected_pixels} ({current_h}x{current_w}) "
# #                      f"对于块位于 ({row_start},{col_start})")
# #                continue # 如果预测数量不对，跳过这个块

# #             # 将一维预测结果重塑为二维掩膜 (current_h, current_w)
# #             block_pred = block_pred_flat.reshape(current_h, current_w)

# #             # 累加预测结果和计数 (使用精确的块范围)
# #             predicted_mask_sum[row_start:row_end, col_start:col_end] += block_pred.astype(np.float32) # 累加浮点数用于平均
# #             count_mask[row_start:row_end, col_start:col_end] += 1

# #     # 处理计数为 0 的区域（理论上在正确填充和步长下不应发生，但作为保险）
# #     count_mask[count_mask == 0] = 1

# #     # 平均重叠区域的预测
# #     predicted_mask_avg = predicted_mask_sum / count_mask
# #     # 四舍五入并转换为 uint8 类型
# #     # 可以根据需要选择不同的取整方式，例如 np.floor, np.ceil
# #     predicted_mask_final = np.round(predicted_mask_avg).astype(np.uint8)

# #     # 裁剪回原始图像大小
# #     return predicted_mask_final[:H, :W]

# # def predict_large_image_with_overlap(model, image, block_size, overlap, predict_func, device=None):
# #     C, H, W = image.shape
# #     block_h, block_w = block_size
# #     overlap_h, overlap_w = overlap
# #     step_h = block_h - overlap_h
# #     step_w = block_w - overlap_w

# #     # 填充图像
# #     pad_h = (step_h - H % step_h) % step_h
# #     pad_w = (step_w - W % step_w) % step_w
# #     padded_image = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode='constant')
# #     padded_H, padded_W = padded_image.shape[1], padded_image.shape[2]

# #     # 初始化预测掩膜和计数掩膜
# #     predicted_mask = np.zeros((padded_H, padded_W), dtype=np.float32)
# #     count_mask = np.zeros((padded_H, padded_W), dtype=np.float32)

# #     # 分块预测
# #     for i in range(0, padded_H - overlap_h, step_h):
# #         for j in range(0, padded_W - overlap_w, step_w):
# #             block = padded_image[:, i:i + block_h, j:j + block_w]
# #             block_tensor = torch.from_numpy(block).float().to(device)
# #             block_pred = predict_func(model, block_tensor, device)
# #             predicted_mask[i:i + block_h, j:j + block_w] += block_pred
# #             count_mask[i:i + block_h, j:j + block_w] += 1

# #     # 平均重叠区域的预测
# #     predicted_mask /= count_mask
# #     predicted_mask = np.round(predicted_mask).astype(np.uint8)
# #     return predicted_mask[:H, :W]


# def inference(argv=None):
#     TASK_ID = int(argv[1])
#     MAPFILE_PATH = argv[2]
#     USER_ID = int(argv[3])
#     MODEL_name = str(argv[4]).split(".")[0]
#     model_scope_str = argv[9]  # 模型作用范围

#     # 类别映射
#     class_mapping = argv[10]

#     # 解析 model_scope
#     try:
#         model_scope = json.loads(model_scope_str)
#         if not model_scope:
#             print("No model scope provided, will process entire image.")
#         else:
#             print("Model scope coordinates:", model_scope)
#     except json.JSONDecodeError as e:
#         print(f"Error decoding model scope: {e}")
#         model_scope_str = None

#     # 连接数据库
#     conn = connect_db()
#     if conn is None:
#         print("无法连接到数据库，程序退出。")
#         return

#     model_inf = fetch_model_from_db(conn,MODEL_name)

#     # 获取地图服务器路径
#     map_servers = fetch_map_server_from_db(conn, TASK_ID)
#     if not map_servers:
#         print(f"task_id {TASK_ID} 未找到地图服务器路径，请检查数据库。")
#         conn.close()
#         return
#     map_name = map_servers[0][0]
#     IMAGE_PATH = os.path.join(MAPFILE_PATH, f"{map_name}.tif")

#     # 获取标签数据
#     labels_data = fetch_labels_from_db(conn, TASK_ID)
#     if not labels_data:
#         print(f"task_id {TASK_ID} 没有找到标签数据，将不使用原始标签掩膜。")
#         labels_data = None

#     # 提取 user_id 和 status
#     user_id = USER_ID
#     status = 0
#     type_arr = fetch_typeid_from_db(conn, TASK_ID)

#     # # 定义模型保存路径
#     model_save_path = model_inf['path']
#     # model_save_dir = "/home/change/labelcode/labelMark/trained_models"
#     # task_model_save_dir = os.path.join(model_save_dir, str(USER_ID))
#     # if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
#     #     model_save_path = os.path.join(task_model_save_dir, "segmentation_results", f"{MODEL_TYPE}.pth")
#     # elif MODEL_TYPE in ["svm", "xgboost"]:
#     #     model_save_path = os.path.join(task_model_save_dir, "segmentation_results", f"{MODEL_TYPE}.joblib")
#     # elif MODEL_TYPE == "yolo":
#     #     model_save_path = os.path.join(task_model_save_dir, "detection_results", f"{MODEL_TYPE}", "weights", "best.pt")
#     # else:
#     #     print(f"未知的模型类型: {MODEL_TYPE}")
#     #     conn.close()
#     #     return

#     # # 加载映射规则
#     # if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
#     #     mapping_path = os.path.join(task_model_save_dir, "segmentation_results", "mapping.json")
#     # elif MODEL_TYPE == "yolo":
#     #     mapping_path = os.path.join(task_model_save_dir, "detection_results", "mapping.json")
#     # if not os.path.exists(mapping_path):
#     #     print(f"映射文件 {mapping_path} 不存在，程序退出。")
#     #     conn.close()
#     #     return
#     # with open(mapping_path, 'r') as f:
#     #     mappings = json.load(f)
#     # if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
#     #     class_index_to_type_id = {int(k): v for k, v in mappings['class_index_to_type_id'].items()}
#     #     background_class_index = mappings['background_class_index']
#     #     type_id_to_class_index = {int(k): v for k, v in mappings['type_id_to_class_index'].items()}
#     # elif MODEL_TYPE == "yolo":
#     #     class_id_to_type_id = {int(k): v for k, v in mappings['class_id_to_type_id'].items()}

#     # 设置设备
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

#     MODEL_TYPE = model_inf['model_type']

#     # 根据模型类型加载模型
#     if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
#         with rasterio.open(IMAGE_PATH) as src:
#             in_channels = src.count
#         num_classes = len(type_arr[0][0].split(",")) + 1
#         if MODEL_TYPE == "light_unet":
#             model = LightUNet(in_channels=in_channels, num_classes=num_classes).to(device)
#         elif MODEL_TYPE == "unet":
#             model = UNet(in_channels=in_channels, num_classes=num_classes).to(device)
#         elif MODEL_TYPE == "fast_scnn":
#             model = FastSCNN(in_channels=in_channels, num_classes=num_classes).to(device)
#         model.load_state_dict(torch.load(model_save_path, map_location=device))
#     elif MODEL_TYPE == "xgboost":
#         model = joblib.load(model_save_path)
#     elif MODEL_TYPE == "yolo":
#         from ultralytics import YOLO
#         model = YOLO(model_save_path)
#     else:
#         print(f"未知的模型类型: {MODEL_TYPE}")
#         conn.close()
#         return

#     # 进行推理
#     if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
#         # 直接加载整个图像
#         with rasterio.open(IMAGE_PATH) as src:
#             image = src.read().astype(np.float32) / 255.0  # (C, H, W)
#             window_transform = src.transform  # 用于后续多边形转换

#         block_size = (1024, 1024)
#         overlap = (128, 128)
#         _, H, W = image.shape

#         if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
#             if H <= block_size[0] and W <= block_size[1]:
#                 image_tensor = torch.from_numpy(image).float().to(device)
#                 predicted_mask = predict_torch_model(model, image_tensor, device)
#             else:
#                 predicted_mask = predict_large_image_with_overlap(
#                     model, image, block_size, overlap, predict_torch_model, device)


#         # # 创建数据集
#         # dataset = RemoteSensingSegmentationDataset(
#         #     IMAGE_PATH, 
#         #     labels_data=labels_data, 
#         #     num_classes=None, 
#         #     type_id_to_class_index=None, 
#         #     background_class_index=None, 
#         #     apply_transforms=False
#         # )
#         # # dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, None, None, None, model_scope_str)

#         # # 定义分块大小
#         # block_size = (1024, 1024)
#         # block_h, block_w = block_size

#         # if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
#         #     image_tensor, _, window_transform = dataset[0]
#         #     image = image_tensor.numpy()
#         #     _, H, W = image.shape
#         #     if H <= block_h and W <= block_w:
#         #         predicted_mask = predict_torch_model(model, image_tensor, device)
#         #     else:
#         #         overlap = (128, 128)
#         #         predicted_mask = predict_large_image_with_overlap(model, image, block_size, overlap, predict_torch_model, device)
#             # image = dataset.image  # (C, H, W)
#             # _, H, W = image.shape
#             # if H <= block_h and W <= block_w:
#             #     # 图像小于分块大小，直接预测
#             #     image_tensor = torch.from_numpy(image).float()
#             #     predicted_mask = predict_torch_model(model, image_tensor, device)
#             # else:
#             #     # 图像大于分块大小，进行分块推理
#             #     overlap = (128, 128)
#             #     predicted_mask = predict_large_image_with_overlap(model, image, block_size, overlap, predict_torch_model, device)
#             #     # predicted_mask = predict_large_image(model, image, block_size, predict_torch_model, device)
#         # elif MODEL_TYPE == "xgboost":
#         #     image_tensor, _, window_transform = dataset[0]
#         #     image = image_tensor.numpy()  # (C, H, W)
#         #     _, H, W = image.shape
#         #     if H <= block_h and W <= block_w:
#         #         X = image.transpose(1, 2, 0).reshape(-1, image.shape[0])
#         #         predicted_mask = predict_sklearn_model(model, X, (None, H, W))
#         #     else:
#         #         overlap = (128, 128)
#         #         predicted_mask = predict_large_image_sklearn_with_overlap(
#         #             model,           # 加载的 XGBoost 模型
#         #             image,           # (C, H, W) NumPy 数组
#         #             block_size,
#         #             overlap
#         #         )
#                 # predicted_mask = predict_large_image_with_overlap(model, image, block_size, overlap, predict_sklearn_model, device)
#             # with rasterio.open(IMAGE_PATH) as src:
#             #     image = src.read()  # (C, H, W)
#             #     image = image.astype(np.float32) / 255.0
#             # _, H, W = image.shape
#             # if H <= block_h and W <= block_w:
#             #     # 图像小于分块大小，直接预测
#             #     X = image.transpose(1, 2, 0).reshape(-1, image.shape[0])
#             #     predicted_mask = predict_sklearn_model(model, X, (None, H, W))
#             # else:
#             #     # 图像大于分块大小，进行分块推理
#             #     overlap = (128, 128)
#             #     predicted_mask = predict_large_image_with_overlap(model, image, block_size, overlap, predict_sklearn_model, device)
#             #     # predicted_mask = predict_large_image(model, image, block_size, predict_sklearn_model)

#         # 后处理掩膜
#         predicted_mask = post_process_mask(
#             predicted_mask, min_object_size=int(argv[5]), hole_size_threshold=int(argv[6]),
#             boundary_smoothing=int(argv[7])
#         )

#         # 转换为多边形
#         segmentation_polygons = identify_holes_and_split(
#             predicted_mask, window_transform,
#             class_index_to_type_id,
#             background_class_index
#         )

#         # 更新数据库结果
#         insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)
#         torch.cuda.empty_cache()

#     elif MODEL_TYPE == "yolo":
#         temp_dir = "temp_inference"
#         os.makedirs(temp_dir, exist_ok=True)
#         jpeg_filename = f"inference_{TASK_ID}.jpg"
#         jpeg_path = os.path.join(temp_dir, jpeg_filename)

#         cropped_image_path, crop_transform = crop_image_by_scope(IMAGE_PATH, model_scope_str)

#         with rasterio.open(cropped_image_path) as src:
#             image = src.read()
#             image = image.transpose(1, 2, 0)
#             if image.shape[2] > 3:
#                 image = image[:, :, :3]
#             image = (image / image.max() * 255).astype(np.uint8)
#             Image.fromarray(image).save(jpeg_path, "JPEG")

#         results = model(jpeg_path, conf=float(argv[5]), imgsz=int(argv[6]))

#         detection_polygons, _, _ = process_yolo_results(
#             results, crop_transform, TASK_ID, user_id, status, conn,
#             class_id_to_type_id, None, cropped_image_path
#         )

#         original_polygons_with_type = []
#         if labels_data:
#             for _, geom_str, type_id, *_ in labels_data:
#                 coords_str_list = geom_str.split(',')
#                 coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i + 1].strip()))
#                                for i in range(0, len(coords_str_list), 2)]
#                 poly = Polygon(coords_list)
#                 original_polygons_with_type.append((poly, type_id))

#         def filter_original_labels(original_polygons_with_type, predicted_polygons, distance_threshold=15):
#             filtered = []
#             all_predicted = [poly for polys in predicted_polygons.values() for poly in polys]
#             predicted_multipoly = MultiPolygon(all_predicted) if all_predicted else MultiPolygon()
#             for orig_poly, type_id in original_polygons_with_type:
#                 orig_centroid = orig_poly.centroid
#                 keep = True
#                 for pred_poly in predicted_multipoly.geoms:
#                     pred_centroid = pred_poly.centroid
#                     if orig_centroid.distance(pred_centroid) < distance_threshold:
#                         keep = False
#                         break
#                 if keep:
#                     filtered.append((orig_poly, type_id))
#             return filtered

#         filtered_original_with_type = filter_original_labels(original_polygons_with_type, detection_polygons,
#                                                              distance_threshold=float(argv[7]))
        
#         print("q")

#         filtered_original_dict = {}
#         for poly, type_id in filtered_original_with_type:
#             if type_id not in filtered_original_dict:
#                 filtered_original_dict[type_id] = []
#             filtered_original_dict[type_id].append(poly)

#         type_ids = set(detection_polygons.keys()) | set(filtered_original_dict.keys())
#         segmentation_polygons = {type_id: filtered_original_dict.get(type_id, []) + detection_polygons.get(type_id, [])
#                                  for type_id in type_ids}

#         delete_existing_results_db(conn, TASK_ID)
#         insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

#         if model_scope:
#             os.remove(jpeg_path)
#         torch.cuda.empty_cache()



#     conn.close()
#     print("推理任务完成!")
