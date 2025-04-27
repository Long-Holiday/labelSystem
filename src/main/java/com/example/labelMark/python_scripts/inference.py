# import json
# import sys
# import os
# import rasterio
# from shapely import MultiPolygon, Polygon
# import torch
# from torch.utils.data import DataLoader
# from ultralytics import YOLO
# from models.light_unet import LightUNet
# from models.unet import UNet
# from models.fast_scnn import FastSCNN
# from models.svm import SVM
# from models.xgboostt import XGBoost
# from utils import (
#     connect_db, crop_image_by_scope, fetch_labels_from_db, delete_existing_results_db,
#     insert_segmentation_results_db, RemoteSensingSegmentationDataset,
#     post_process_mask, identify_holes_and_split,
#     process_yolo_results, draw_boxes_on_image,
#     fetch_map_server_from_db,fetch_typeid_from_db,create_original_label_mask
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
#             outputs = torch.nn.functional.interpolate(outputs, size=image_tensor.shape[2:], mode='bilinear', align_corners=False)
#         probabilities = torch.softmax(outputs, dim=1)
#         predicted_mask = torch.argmax(probabilities, dim=1).squeeze().cpu().numpy()
#     return predicted_mask.astype(np.uint8)

# def predict_sklearn_model(model, X, image_shape):
#     """使用 scikit-learn 模型进行预测"""
#     predictions = model.predict(X)
#     return predictions.reshape(image_shape[1], image_shape[2]).astype(np.uint8)

# def main():
#     # # 检查命令行参数
#     # if len(sys.argv) != 4:
#     #     print("Usage: python inference.py <task_id> <mapfile_path> <model_type>")
#     #     sys.exit(1)

#     TASK_ID = int(sys.argv[1])
#     MAPFILE_PATH = sys.argv[2]
#     USER_ID = int(sys.argv[3])
#     MODEL_TYPE = str(sys.argv[4]).split(".")[0]
#     model_scope_str = sys.argv[9]  # 模型作用范围

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

#     # TASK_ID = 136
#     # IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"
#     # MODEL_TYPE = "yolo"  # 可选: "light_unet", "unet", "fast_scnn", "svm", "xgboost"
#     # USER_ID = 10

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
#     map_name = map_servers[0][0]
#     IMAGE_PATH = os.path.join(MAPFILE_PATH, f"{map_name}.tif")

#     # 获取标签数据
#     labels_data = fetch_labels_from_db(conn, TASK_ID)
#     if not labels_data:
#         print(f"task_id {TASK_ID} 没有找到标签数据，将不使用原始标签掩膜。")
#         labels_data = None  # 如果没有标签数据，设为 None

#     # 提取 user_id 和 status
#     user_id = USER_ID
#     status = 0
#     type_arr = fetch_typeid_from_db(conn, TASK_ID)
#     print(len(type_arr[0][0].split(",")))

#     # 定义模型保存路径
#     model_save_dir = "/home/change/labelcode/labelMark/trained_models"
#     task_model_save_dir = os.path.join(model_save_dir, str(USER_ID))
#     if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
#         model_save_path = os.path.join(task_model_save_dir, "segmentation_results", f"{MODEL_TYPE}.pth")
#     elif MODEL_TYPE in ["svm", "xgboost"]:
#         model_save_path = os.path.join(task_model_save_dir, "segmentation_results", f"{MODEL_TYPE}.joblib")
#     elif MODEL_TYPE == "yolo":
#         model_save_path = os.path.join(task_model_save_dir,"detection_results", f"{MODEL_TYPE}", "weights", "best.pt")
#     else:
#         print(f"未知的模型类型: {MODEL_TYPE}")
#         conn.close()
#         return
    
#     # 加载映射规则
#     if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "svm", "xgboost"]:
#         mapping_path = os.path.join(task_model_save_dir, "segmentation_results","mapping.json")
#     elif MODEL_TYPE == "yolo":
#         mapping_path = os.path.join(task_model_save_dir, "detection_results", "mapping.json")
#     if not os.path.exists(mapping_path):
#         print(f"映射文件 {mapping_path} 不存在，程序退出。")
#         conn.close()
#         return
#     with open(mapping_path, 'r') as f:
#         mappings = json.load(f)
#     if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "svm", "xgboost"]:
#         class_index_to_type_id = {int(k): v for k, v in mappings['class_index_to_type_id'].items()}
#         background_class_index = mappings['background_class_index']
#         type_id_to_class_index = {int(k): v for k, v in mappings['type_id_to_class_index'].items()}  # 新增，用于创建掩膜
#     elif MODEL_TYPE == "yolo":
#         class_id_to_type_id = {int(k): v for k, v in mappings['class_id_to_type_id'].items()}

#     # 设置设备
#     device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

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
#     elif MODEL_TYPE in ["svm", "xgboost"]:
#         model = joblib.load(model_save_path)
#     elif MODEL_TYPE == "yolo":
#         model = YOLO(model_save_path)
#     else:
#         print(f"未知的模型类型: {MODEL_TYPE}")
#         conn.close()
#         return

#     # 进行推理
#     if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "svm", "xgboost"]:
#         # 创建数据集，支持可选的标签数据
#         dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, None, None, None, model_scope_str)
#         # dataset = RemoteSensingSegmentationDataset(IMAGE_PATH)

#         if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
#             image_tensor = torch.from_numpy(dataset.image).float()
#             predicted_mask = predict_torch_model(model, image_tensor, device)
#         elif MODEL_TYPE in ["svm", "xgboost"]:
#             with rasterio.open(IMAGE_PATH) as src:
#                 image = src.read()
#                 image = image.astype(np.float32) / 255.0
#                 image = image.transpose(1, 2, 0)
#             X = image.reshape(-1, image.shape[2])
#             H, W = image.shape[0], image.shape[1]
#             predicted_mask = predict_sklearn_model(model, X, (None, H, W))

#         # 后处理掩膜
#         predicted_mask = post_process_mask(
#             predicted_mask, min_object_size=int(sys.argv[5]), hole_size_threshold=int(sys.argv[6]),
#             boundary_smoothing=int(sys.argv[7])
#         )


#         # 如果有标签数据，创建并应用原始标签掩膜（新增）
#         # if labels_data:
#         #     original_mask = create_original_label_mask(
#         #         labels_data,
#         #         dataset.transform,
#         #         dataset.image.shape[1],
#         #         dataset.image.shape[2],
#         #         background_class_index,
#         #         type_id_to_class_index
#         #     )
#         #     predicted_mask = np.where(original_mask != background_class_index, original_mask, predicted_mask)

#         # 转换为多边形
#         segmentation_polygons = identify_holes_and_split(
#             predicted_mask, dataset.transform,
#             class_index_to_type_id,
#             background_class_index
#         )

#         # 更新数据库结果
#         # delete_existing_results_db(conn, TASK_ID)
#         insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

#     elif MODEL_TYPE == "yolo":
#         # 创建临时目录并定义 JPEG 文件路径
#         temp_dir = "temp_inference"
#         os.makedirs(temp_dir, exist_ok=True)
#         jpeg_filename = f"inference_{TASK_ID}.jpg"
#         jpeg_path = os.path.join(temp_dir, jpeg_filename)
        
#         cropped_image_path, crop_transform = crop_image_by_scope(IMAGE_PATH, model_scope_str)
        
#         # 将 TIFF 转换为 JPEG
#         with rasterio.open(cropped_image_path) as src:
#             image = src.read()
#             image = image.transpose(1, 2, 0)
#             if image.shape[2] > 3:
#                 image = image[:, :, :3]
#             image = (image / image.max() * 255).astype(np.uint8)
#             Image.fromarray(image).save(jpeg_path, "JPEG")
        
#         # 执行 YOLO 推理
#         results = model(jpeg_path, conf=float(sys.argv[5]), imgsz=int(sys.argv[6]))
        
#         # # 获取原始 TIFF 图像的变换信息
#         # with rasterio.open(IMAGE_PATH) as src:
#         #     original_transform = src.transform
        
#         # 处理 YOLO 检测结果
#         detection_polygons, _, _ = process_yolo_results(
#             results, crop_transform, TASK_ID, user_id, status, conn,
#             class_id_to_type_id, None, cropped_image_path
#         )

#         # 处理原始标注并保留类型信息
#         original_polygons_with_type = []
#         if labels_data:
#             for _, geom_str, type_id, *_ in labels_data:
#                 coords_str_list = geom_str.split(',')
#                 coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
#                             for i in range(0, len(coords_str_list), 2)]
#                 poly = Polygon(coords_list)
#                 original_polygons_with_type.append((poly, type_id))

#         # 过滤重叠的原始标注
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

#         filtered_original_with_type = filter_original_labels(original_polygons_with_type, detection_polygons,distance_threshold=float(sys.argv[7]))

#         # 按类型分组
#         filtered_original_dict = {}
#         for poly, type_id in filtered_original_with_type:
#             if type_id not in filtered_original_dict:
#                 filtered_original_dict[type_id] = []
#             filtered_original_dict[type_id].append(poly)

#         # 合并预测和原始多边形
#         type_ids = set(detection_polygons.keys()) | set(filtered_original_dict.keys())
#         segmentation_polygons = {type_id: filtered_original_dict.get(type_id, []) + detection_polygons.get(type_id, []) 
#                                 for type_id in type_ids}

#         # 删除临时文件
#         if model_scope:
#             os.remove(jpeg_path)

#         # 更新数据库结果
#         # delete_existing_results_db(conn, TASK_ID)
#         insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

#     # elif MODEL_TYPE == "yolo":
#     #     # 创建临时目录并定义 JPEG 文件路径
#     #     temp_dir = "temp_inference"
#     #     os.makedirs(temp_dir, exist_ok=True)  # 如果目录不存在则创建
#     #     jpeg_filename = f"inference_{TASK_ID}.jpg"
#     #     jpeg_path = os.path.join(temp_dir, jpeg_filename)
        
#     #     # 将 TIFF 转换为 JPEG
#     #     with rasterio.open(IMAGE_PATH) as src:
#     #         image = src.read()  # 读取所有波段
#     #         image = image.transpose(1, 2, 0)  # 转换为 HWC 格式
#     #         if image.shape[2] > 3:
#     #             image = image[:, :, :3]  # 仅保留前 3 个波段 (RGB)
#     #         # 归一化到 0-255
#     #         image = (image / image.max() * 255).astype(np.uint8)
#     #         Image.fromarray(image).save(jpeg_path, "JPEG")  # 保存为 JPEG
        
#     #     # 执行 YOLO 推理
#     #     results = model(jpeg_path, conf=float(sys.argv[5]), imgsz=int(sys.argv[6]))
        
#     #     # 获取原始 TIFF 图像的变换信息
#     #     with rasterio.open(IMAGE_PATH) as src:
#     #         original_transform = src.transform
        
#     #     # 处理 YOLO 检测结果
#     #     detection_polygons, _, _ = process_yolo_results(
#     #         results, original_transform, TASK_ID, user_id, status, conn,
#     #         class_id_to_type_id,  # 使用加载的映射
#     #         None, IMAGE_PATH
#     #     )
#     #     segmentation_polygons = detection_polygons
        
#     #     # 删除临时文件
#     #     if model_scope:
#     #         # os.remove(cropped_image_path)
#     #         os.remove(jpeg_path)
#     #         # print(f"已删除临时文件: {cropped_image_path}, {jpeg_path}")
#     #     # 删除临时 JPEG 文件
#     #     # os.remove(jpeg_path)


#     # 关闭数据库连接
#     conn.close()
#     print("推理任务完成!")

# if __name__ == "__main__":
#     main()

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
from utils import (
    connect_db, crop_image_by_scope, fetch_labels_from_db, delete_existing_results_db, filter_original_labels,
    insert_segmentation_results_db, RemoteSensingSegmentationDataset,
    post_process_mask, identify_holes_and_split,
    process_yolo_results, draw_boxes_on_image,
    fetch_map_server_from_db, fetch_typeid_from_db, create_original_label_mask
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
            outputs = torch.nn.functional.interpolate(outputs, size=image_tensor.shape[2:], mode='bilinear', align_corners=False)
        probabilities = torch.softmax(outputs, dim=1)
        predicted_mask = torch.argmax(probabilities, dim=1).squeeze().cpu().numpy()
    return predicted_mask.astype(np.uint8)

def predict_sklearn_model(model, X, image_shape):
    """使用 scikit-learn 模型进行预测"""
    predictions = model.predict(X)
    return predictions.reshape(image_shape[1], image_shape[2]).astype(np.uint8)

def predict_large_image(model, image, block_size, predict_func, device=None):
    """
    对大型图像进行分块推理
    
    参数:
        model: 加载的模型
        image: 输入图像，形状为 (C, H, W)
        block_size: 分块大小，例如 (1024, 1024)
        predict_func: 预测函数（predict_torch_model 或 predict_sklearn_model）
        device: PyTorch 设备（对于 PyTorch 模型）
    
    返回:
        predicted_mask: 完整图像的预测掩膜
    """
    C, H, W = image.shape
    block_h, block_w = block_size

    # 计算填充大小，使图像尺寸能被块大小整除
    pad_h = (block_h - H % block_h) % block_h
    pad_w = (block_w - W % block_w) % block_w

    # 填充图像
    padded_image = np.pad(image, ((0, 0), (0, pad_h), (0, pad_w)), mode='constant')
    padded_C, padded_H, padded_W = padded_image.shape

    # 初始化完整掩膜
    predicted_mask = np.zeros((padded_H, padded_W), dtype=np.uint8)

    # 分块预测
    for i in range(0, padded_H, block_h):
        for j in range(0, padded_W, block_w):
            block = padded_image[:, i:i+block_h, j:j+block_w]
            if device:  # PyTorch 模型
                block_tensor = torch.from_numpy(block).float().to(device)
                block_pred = predict_func(model, block_tensor, device)
            else:  # scikit-learn 模型
                X_block = block.transpose(1, 2, 0).reshape(-1, block.shape[0])
                block_pred = predict_func(model, X_block, (None, block_h, block_w))
            predicted_mask[i:i+block_h, j:j+block_w] = block_pred

    # 裁剪回原始图像大小
    predicted_mask = predicted_mask[:H, :W]
    return predicted_mask

def main():
    TASK_ID = int(sys.argv[1])
    MAPFILE_PATH = sys.argv[2]
    USER_ID = int(sys.argv[3])
    MODEL_TYPE = str(sys.argv[4]).split(".")[0]
    model_scope_str = sys.argv[9]  # 模型作用范围

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
    type_arr = fetch_typeid_from_db(conn, TASK_ID)

    # 定义模型保存路径
    model_save_dir = "/home/change/labelcode/labelMark/trained_models"
    task_model_save_dir = os.path.join(model_save_dir, str(USER_ID))
    if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
        model_save_path = os.path.join(task_model_save_dir, "segmentation_results", f"{MODEL_TYPE}.pth")
    elif MODEL_TYPE in ["svm", "xgboost"]:
        model_save_path = os.path.join(task_model_save_dir, "segmentation_results", f"{MODEL_TYPE}.joblib")
    elif MODEL_TYPE == "yolo":
        model_save_path = os.path.join(task_model_save_dir, "detection_results", f"{MODEL_TYPE}", "weights", "best.pt")
    else:
        print(f"未知的模型类型: {MODEL_TYPE}")
        conn.close()
        return

    # 加载映射规则
    if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
        mapping_path = os.path.join(task_model_save_dir, "segmentation_results", "mapping.json")
    elif MODEL_TYPE == "yolo":
        mapping_path = os.path.join(task_model_save_dir, "detection_results", "mapping.json")
    if not os.path.exists(mapping_path):
        print(f"映射文件 {mapping_path} 不存在，程序退出。")
        conn.close()
        return
    with open(mapping_path, 'r') as f:
        mappings = json.load(f)
    if MODEL_TYPE in ["light_unet", "unet", "fast_scnn", "xgboost"]:
        class_index_to_type_id = {int(k): v for k, v in mappings['class_index_to_type_id'].items()}
        background_class_index = mappings['background_class_index']
        type_id_to_class_index = {int(k): v for k, v in mappings['type_id_to_class_index'].items()}
    elif MODEL_TYPE == "yolo":
        class_id_to_type_id = {int(k): v for k, v in mappings['class_id_to_type_id'].items()}

    # 设置设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 根据模型类型加载模型
    if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
        with rasterio.open(IMAGE_PATH) as src:
            in_channels = src.count
        num_classes = len(type_arr[0][0].split(",")) + 1
        if MODEL_TYPE == "light_unet":
            model = LightUNet(in_channels=in_channels, num_classes=num_classes).to(device)
        elif MODEL_TYPE == "unet":
            model = UNet(in_channels=in_channels, num_classes=num_classes).to(device)
        elif MODEL_TYPE == "fast_scnn":
            model = FastSCNN(in_channels=in_channels, num_classes=num_classes).to(device)
        model.load_state_dict(torch.load(model_save_path, map_location=device))
    elif MODEL_TYPE =="xgboost" :
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
        # 创建数据集
        dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, None, None, None, model_scope_str)

        # 定义分块大小
        block_size = (1024, 1024)
        block_h, block_w = block_size

        if MODEL_TYPE in ["light_unet", "unet", "fast_scnn"]:
            image = dataset.image  # (C, H, W)
            _, H, W = image.shape
            if H <= block_h and W <= block_w:
                # 图像小于分块大小，直接预测
                image_tensor = torch.from_numpy(image).float()
                predicted_mask = predict_torch_model(model, image_tensor, device)
            else:
                # 图像大于分块大小，进行分块推理
                predicted_mask = predict_large_image(model, image, block_size, predict_torch_model, device)
        elif MODEL_TYPE == "xgboost":
            with rasterio.open(IMAGE_PATH) as src:
                image = src.read()  # (C, H, W)
                image = image.astype(np.float32) / 255.0
            _, H, W = image.shape
            if H <= block_h and W <= block_w:
                # 图像小于分块大小，直接预测
                X = image.transpose(1, 2, 0).reshape(-1, image.shape[0])
                predicted_mask = predict_sklearn_model(model, X, (None, H, W))
            else:
                # 图像大于分块大小，进行分块推理
                predicted_mask = predict_large_image(model, image, block_size, predict_sklearn_model)

        # 后处理掩膜
        predicted_mask = post_process_mask(
            predicted_mask, min_object_size=int(sys.argv[5]), hole_size_threshold=int(sys.argv[6]),
            boundary_smoothing=int(sys.argv[7])
        )

        # 转换为多边形
        segmentation_polygons = identify_holes_and_split(
            predicted_mask, dataset.transform,
            class_index_to_type_id,
            background_class_index
        )

        # 更新数据库结果
        insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

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
        
        results = model(jpeg_path, conf=float(sys.argv[5]), imgsz=int(sys.argv[6]))
        
        detection_polygons, _, _ = process_yolo_results(
            results, crop_transform, TASK_ID, user_id, status, conn,
            class_id_to_type_id, None, cropped_image_path
        )

        original_polygons_with_type = []
        if labels_data:
            for _, geom_str, type_id, *_ in labels_data:
                coords_str_list = geom_str.split(',')
                coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
                            for i in range(0, len(coords_str_list), 2)]
                poly = Polygon(coords_list)
                original_polygons_with_type.append((poly, type_id))



        filtered_original_with_type = filter_original_labels(original_polygons_with_type, detection_polygons, distance_threshold=float(sys.argv[7]))

        filtered_original_dict = {}
        for poly, type_id in filtered_original_with_type:
            if type_id not in filtered_original_dict:
                filtered_original_dict[type_id] = []
            filtered_original_dict[type_id].append(poly)

        type_ids = set(detection_polygons.keys()) | set(filtered_original_dict.keys())
        segmentation_polygons = {type_id: filtered_original_dict.get(type_id, []) + detection_polygons.get(type_id, []) 
                                for type_id in type_ids}

        if model_scope:
            os.remove(jpeg_path)

        insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)

    conn.close()
    print("推理任务完成!")

if __name__ == "__main__":
    main()