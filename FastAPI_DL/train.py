import json
import copy
import os
import tempfile
import numpy as np
import rasterio
from fastapi import APIRouter
from shapely import MultiPolygon, Polygon
import shutil
import torch
from torch.utils.data import DataLoader

from shapely import Point, buffer, coverage_union_all, envelope
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds


from inference import predict_large_image_with_overlap
from models.light_unet import LightUNet
from models.unet import UNet
from models.fast_scnn import FastSCNN
from models.xgboostt import XGBoost
from dataset import RemoteSensingSegmentationDataset
from trainers import train_torch_model, predict_torch_model, train_sklearn_model, predict_sklearn_model
from utils import (cleanup_training_files, connect_db, crop_image_by_scope, crop_tiff_by_polygon, delete_point_results_db, fetch_labels_from_db, delete_existing_results_db, generate_bounding_boxes, generate_point_coordinates_sam, identify_holes_and_split_SAM, 
                  insert_segmentation_results_db, match_typeid_to_name, 
                  post_process_mask, post_process_mask_sam, save_model_to_db, visualize_results, visualize_original_mask,
                  identify_holes_and_split, prepare_data_for_sklearn, fetch_map_server_from_db,
                  process_yolo_results, create_yolo_dataset, create_yolo_data_yaml, draw_boxes_on_image,create_original_label_mask)

router = APIRouter()
global_sam = None
global_yolo = None

@router.on_event("startup")
async def load_model():
    # from samgeo import SamGeo2
    # # from samgeo import SamGeo
    # global global_sam
    # if global_sam is None:
    #     global_sam = SamGeo2(  # 延迟实例化到启动事件
    #         model_id="sam2-hiera-base-plus",
    #         # model_id="sam2-hiera-small",
    #         automatic=False,
    #         device="cuda",
    #     )
    #     # global_sam = SamGeo(  # 延迟实例化到启动事件
    #     #     model_id="vit_b",
    #     #     automatic=False,
    #     #     device="cuda",
    #     # )
    # print("SamGeo 已实例化")

    from ultralytics import YOLO
    global global_yolo
    if global_yolo is None:
        global_yolo = YOLO("yolo11m-obb.pt")
    print("YOLO 模型已加载")

def train_function(argv=None):
    # time.sleep(20)
    # print(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8])
    # 初始化设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 连接数据库
    # conn = db_conn
    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return

    # 配置参数
    # TASK_ID = 135
    # IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"
    # MODEL_TYPE = "sam"  # 可选: "light_unet", "unet", "fast_scnn", "svm", "xgboost"
    # BATCH_SIZE = 10
    # LEARNING_RATE = 0.001
    # NUM_EPOCHS = 150
    # model_scope_str = json.dumps([])
    # USER_ID = 10

    TASK_ID = int(argv[1])
    MAPFILE_PATH = argv[2]
    MODEL_TYPE = argv[3]
    BATCH_SIZE = 32
    LEARNING_RATE = 0.001
    NUM_EPOCHS = int(argv[4])
    USER_ID = int(argv[9])

    model_scope_str = argv[10]  # 模型作用范围
    model_name = argv[11]

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
    

    # 模型保存路径
    model_save_dir = "/home/change/labelcode/labelMark/trained_models"
    # 修改模型保存路径，加入 task_id 文件夹
    task_model_save_dir = os.path.join(model_save_dir, str(USER_ID)) # 创建 task_id 文件夹路径
    # 检查文件夹是否存在，如果不存在则创建
    if not os.path.exists(task_model_save_dir):
        os.makedirs(task_model_save_dir, exist_ok=True) # 使用 makedirs 递归创建目录，exist_ok=True 表示目录已存在时不会报错
    detection_output_dir = os.path.join(task_model_save_dir, "detection_results")
    segmentation_output_dir = os.path.join(task_model_save_dir, "segmentation_results")
    if not os.path.exists(detection_output_dir):
        os.makedirs(detection_output_dir, exist_ok=True)
    if not os.path.exists(segmentation_output_dir):
        os.makedirs(segmentation_output_dir, exist_ok=True)

    #yolo模型参数
    CONF_THRESHOLD = float(argv[5]) if argv[5] else None # 置信度阈值
    IMG_SIZE = int(argv[6]) if argv[6] else None# 输入图像尺寸

    # 获取地图服务器路径
    map_servers = fetch_map_server_from_db(conn, TASK_ID)
    if not map_servers:
        print(f"task_id {TASK_ID} 未找到地图服务器路径，请检查数据库。")
        conn.close()
        return
    # 假设 map_server 是单条记录，取第一个值
    map_name = map_servers[0][0]  # fetchall 返回元组列表，提取第一个元组的第一个元素
    # IMAGE_PATH = f"{MAPFILE_PATH}/{map_name}.tif"  # 修正路径拼接，使用斜杠分隔
    IMAGE_PATH = os.path.join(f"{MAPFILE_PATH}", f"{map_name}.tif") 

    # 获取标签数据
    labels_data = fetch_labels_from_db(conn, TASK_ID)
    if not labels_data:
        print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
        conn.close()
        return

    # 提取 user_id 和 status
    user_ids = set(row[3] for row in labels_data)
    if len(user_ids) > 1:
        print(f"警告: task_id {TASK_ID} 包含多个 user_id: {user_ids}，使用第一个")
    user_id = labels_data[0][3]
    status = labels_data[0][5]

    # 动态确定分类数量
    type_ids_from_db = sorted(list(set(row[2] for row in labels_data)))

    # 获取所有 type_ids
    type_ids = set(row[2] for row in labels_data)

    if MODEL_TYPE in ["light_unet", "unet","fast_scnn", "xgboost"]:
        # 类别映射
        num_classes = len(type_ids_from_db) + 1
        type_id_to_class_index = {type_id: idx for idx, type_id in enumerate(type_ids_from_db)}
        background_class_index = num_classes - 1
        class_index_to_type_id = {idx: type_id for type_id, idx in type_id_to_class_index.items()}

        # # 保存映射规则到 JSON 文件(需要修改)
        # mapping_path = os.path.join(segmentation_output_dir, "mapping.json")
        # with open(mapping_path, 'w') as f:
        #     json.dump({
        #         'type_id_to_class_index': type_id_to_class_index,
        #         'class_index_to_type_id': {str(k): v for k, v in class_index_to_type_id.items()},  # JSON 键必须为字符串
        #         'background_class_index': background_class_index
        #     }, f)
        # print(f"映射规则已保存至: {mapping_path}")
        # 获取 type_id 到 type_name 的映射

        # 创建数据集
        train_dataset = RemoteSensingSegmentationDataset(
                IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, 
                background_class_index, apply_transforms=True
            )
        # dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, num_classes, 
        #                                          type_id_to_class_index, background_class_index, 
        #                                          model_scope_str)
        # dataset = RemoteSensingSegmentationDataset(IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, background_class_index)
        # visualize_original_mask(dataset.label_mask, num_classes)

        # 模型选择和训练
        if MODEL_TYPE in ["light_unet", "unet","fast_scnn"]:
            # 训练数据集（启用变换）
            dataloader = DataLoader(train_dataset, batch_size=BATCH_SIZE)

            # 加载模型
            with rasterio.open(IMAGE_PATH) as src:
                in_channels = src.count
            if MODEL_TYPE == "light_unet":
                model = LightUNet(in_channels=in_channels, num_classes=num_classes).to(device)
            elif MODEL_TYPE == "unet":
                model = UNet(in_channels=in_channels, num_classes=num_classes).to(device)
            elif MODEL_TYPE == "fast_scnn":
                model = FastSCNN(in_channels=in_channels, num_classes=num_classes).to(device)

            criterion = torch.nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
            model_save_path = os.path.join(segmentation_output_dir, f"{model_name}.pth")
            train_torch_model(model, dataloader, criterion, optimizer, NUM_EPOCHS, device, model_save_path)

            # 预测
            with rasterio.open(IMAGE_PATH) as src:
                image = src.read().astype(np.float32) / 255.0
                window_transform = src.transform
            block_size = (1024, 1024)
            overlap = (128, 128)
            _, H, W = image.shape
            if H <= block_size[0] and W <= block_size[1]:
                image_tensor = torch.from_numpy(image).float().to(device)
                predicted_mask = predict_torch_model(model, image_tensor, device)
            else:
                predicted_mask = predict_large_image_with_overlap(
                model, image, block_size, overlap, predict_torch_model, device)

        # if MODEL_TYPE in ["light_unet", "unet","fast_scnn"]:
            #     # 训练数据集（启用变换）
        #     dataloader = DataLoader(train_dataset, batch_size=BATCH_SIZE)

        #     # 加载模型
        #     with rasterio.open(IMAGE_PATH) as src:
        #         in_channels = src.count
        #     if MODEL_TYPE == "light_unet":
        #         model = LightUNet(in_channels=in_channels, num_classes=num_classes).to(device)
        #     elif MODEL_TYPE == "unet":
        #         model = UNet(in_channels=in_channels, num_classes=num_classes).to(device)
        #     elif MODEL_TYPE == "fast_scnn":
        #         model = FastSCNN(in_channels=in_channels, num_classes=num_classes).to(device)

        #     criterion = torch.nn.CrossEntropyLoss()
        #     optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
        #     model_save_path = os.path.join(segmentation_output_dir, f"{MODEL_TYPE}.pth")
        #     train_torch_model(model, dataloader, criterion, optimizer, NUM_EPOCHS, device, model_save_path)

        #     # 预测时禁用变换
        #     pred_dataset = RemoteSensingSegmentationDataset(
        #         IMAGE_PATH, labels_data, num_classes, type_id_to_class_index, 
        #         background_class_index, apply_transforms=False
        #     )
        #     image_tensor, _, window_transform = pred_dataset[0]
        #     predicted_mask = predict_torch_model(model, image_tensor, device)


            # image_tensor = torch.from_numpy(pred_dataset.image).float()
            # predicted_mask = predict_torch_model(model, image_tensor, device)
            '''增加几何变换数据增强'''
            # dataloader = DataLoader(dataset, batch_size=BATCH_SIZE)
            # with rasterio.open(IMAGE_PATH) as src:
            #     in_channels = src.count
            # if MODEL_TYPE == "light_unet":
            #     model = LightUNet(in_channels=in_channels, num_classes=num_classes).to(device)
            # elif MODEL_TYPE == "unet":
            #     model = UNet(in_channels=in_channels, num_classes=num_classes).to(device)
            # elif MODEL_TYPE == "fast_scnn":
            #     model = FastSCNN(in_channels=in_channels, num_classes=num_classes).to(device)

            # criterion = torch.nn.CrossEntropyLoss()
            # optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
            # # 构建包含 task_id 文件夹的模型保存路径
            # model_save_path = os.path.join(segmentation_output_dir, f"{MODEL_TYPE}.pth")
            # train_torch_model(model, dataloader, criterion, optimizer, NUM_EPOCHS, device, model_save_path) # 传递保存路径
            # # train_torch_model(model, dataloader, criterion, optimizer, NUM_EPOCHS, device)
            # image_tensor = torch.from_numpy(dataset.image).float()
            # predicted_mask = predict_torch_model(model, image_tensor, device)
            
        elif MODEL_TYPE =="xgboost":
            image, label_mask, window_transform = train_dataset[0]
            X, y = prepare_data_for_sklearn(image.numpy(), label_mask.numpy())
            model = XGBoost(num_classes, num_round=NUM_EPOCHS)
            model_save_path = os.path.join(segmentation_output_dir, f"{model_name}.joblib") 
            train_sklearn_model(model, X, y, model_save_path)
            predicted_mask = predict_sklearn_model(model, X, image.shape)
            # X, y = prepare_data_for_sklearn(train_dataset.image, train_dataset.label_mask)
            # model = XGBoost(num_classes, num_round=NUM_EPOCHS)
            # # 构建包含 task_id 文件夹的模型保存路径, 使用 .joblib 扩展名
            # model_save_path = os.path.join(segmentation_output_dir, f"{MODEL_TYPE}.joblib") # XGBoost uses joblib
            # train_sklearn_model(model, X, y, model_save_path) # 传递保存路径
            # predicted_mask = predict_sklearn_model(model, X, train_dataset.image.shape)


        # 后处理掩膜
        # predicted_mask = post_process_mask(predicted_mask, min_object_size=500, hole_size_threshold=500, boundary_smoothing=5, mode_filter_size=15)
        predicted_mask = post_process_mask(
            predicted_mask, min_object_size=int(argv[5]), hole_size_threshold=int(argv[6]),
            boundary_smoothing=int(argv[7]))

        # # 创建原始标签掩膜
        # original_mask = create_original_label_mask(
        #     labels_data, 
        #     dataset.transform, 
        #     dataset.image.shape[1], 
        #     dataset.image.shape[2], 
        #     background_class_index, 
        #     type_id_to_class_index
        # )

        # # 将原始标签掩膜覆盖到预测掩膜上
        # predicted_mask = np.where(original_mask != background_class_index, original_mask, predicted_mask)

        # 转换为多边形
        segmentation_polygons = identify_holes_and_split(predicted_mask, window_transform, class_index_to_type_id, background_class_index)
        # segmentation_polygons = identify_holes_and_split(predicted_mask, dataset.transform, class_index_to_type_id, background_class_index)

        # 删除旧结果并写入新结果
        # delete_existing_results_db(conn, TASK_ID)
        insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)
        torch.cuda.empty_cache()

        type_id_to_name = match_typeid_to_name(conn, table_name="type")
        if not type_id_to_name:
            print("无法获取 type_id 到 type_name 的映射，跳过保存映射规则。")
        else:
            mapping_parts = [
                    f"通道 {idx} 对应类别 {type_id_to_name.get(type_id, '未知类别')}"
                    for idx, type_id in class_index_to_type_id.items()
                ]
            mapping_parts.append(f"通道 {background_class_index} 对应背景")
            mapping_data = "; ".join(mapping_parts)

            # 将映射规则保存到数据库
            with rasterio.open(IMAGE_PATH) as src:
                input_num = src.count  # 输入通道数

            tasktype = argv[12]
            print("tasktype" + tasktype)

            save_model_to_db(
                conn=conn,
                model_name=model_name,
                user_id=user_id,
                mapping=mapping_data,
                model_path=model_save_path,
                input_num=input_num,
                output_num=num_classes,
                model_type=MODEL_TYPE,
                tasktype=tasktype,
            )

        # 可视化结果
        # visualize_results(dataset.image, dataset.label_mask, predicted_mask, num_classes)

    elif MODEL_TYPE in ["yolo"]:
        # from ultralytics import YOLO
        # 裁剪影像
        cropped_image_path, crop_transform = crop_image_by_scope(IMAGE_PATH, model_scope_str)

        # 使用临时目录创建 YOLO 数据集
        with tempfile.TemporaryDirectory() as output_dir:
            images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels = create_yolo_dataset(
                labels_data, cropped_image_path, output_dir, model_scope_str
            )

            class_id_to_type_id = {v: k for k, v in type_id_to_class_id.items()}
            print(f"type_id 到 class_id 映射: {type_id_to_class_id}")
            print(f"class_id 到 type_id 映射: {class_id_to_type_id}")
            # mapping_path = os.path.join(detection_output_dir, "mapping.json")
            # with open(mapping_path, 'w') as f:
            #     json.dump({
            #         'type_id_to_class_id': type_id_to_class_id,
            #         'class_id_to_type_id': {str(v): k for k, v in type_id_to_class_id.items()}
            #     }, f)
            # print(f"映射规则已保存至: {mapping_path}")
            # 获取 type_id 到 type_name 的映射
            type_id_to_name = match_typeid_to_name(conn, table_name="type")
            if not type_id_to_name:
                print("无法获取 type_id 到 type_name 的映射，跳过保存映射规则。")
            else:
                # 构建输出通道到类别名称的映射
                channel_to_name = {
                    str(class_id): type_id_to_name.get(type_id, "未知类别")
                    for type_id, class_id in type_id_to_class_id.items()
                }



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

            # 训练 YOLO 模型
            model = copy.deepcopy(global_yolo)
            # model = YOLO("yolo11m-obb.pt")
            train_results = model.train(
                data=data_yaml_path,
                epochs=NUM_EPOCHS,
                imgsz=IMG_SIZE,
                device=device,
                project=detection_output_dir,
                name=f"{MODEL_TYPE}",
                save=True,
                patience=10,
            )

            # 推理
            inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
            results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=IMG_SIZE, save=True, save_txt=True)

            # 使用裁剪后的变换或原始变换
            transform = crop_transform if crop_transform else rasterio.open(IMAGE_PATH).transform

            # 处理检测结果
            detection_polygons, detection_boxes, detection_labels = process_yolo_results(
                results, transform, TASK_ID, user_id, status, conn, class_id_to_type_id, inference_output_path, cropped_image_path
            )

            # 将原始标注转换为 Shapely 多边形
            original_polygons = []
            for _, geom_str, _, *_ in labels_data:
                coords_str_list = geom_str.split(',')
                coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
                            for i in range(0, len(coords_str_list), 2)]
                original_polygons.append(Polygon(coords_list))

            def filter_original_labels(original_polygons, predicted_polygons, distance_threshold=15):

                filtered_original = []
                # Flatten predicted_polygons into a list of Polygon objects and create MultiPolygon
                all_predicted = [poly for polys in predicted_polygons.values() for poly in polys]
                predicted_multipoly = MultiPolygon(all_predicted) if all_predicted else MultiPolygon()
                
                for orig_poly in original_polygons:
                    orig_centroid = orig_poly.centroid
                    keep = True
                    # Iterate over individual Polygon objects in MultiPolygon using .geoms
                    for pred_poly in predicted_multipoly.geoms:
                        pred_centroid = pred_poly.centroid
                        if orig_centroid.distance(pred_centroid) < distance_threshold:
                            keep = False
                            break
                    if keep:
                        filtered_original.append(orig_poly)
                return filtered_original

            filtered_original_polygons = filter_original_labels(original_polygons, detection_polygons, distance_threshold=float(argv[7]))

            # 合并过滤后的原始标注和预测标注
            all_polygons = {type_id: filtered_original_polygons + detection_polygons.get(type_id, []) 
                            for type_id in type_ids}

            # 写入数据库
            delete_existing_results_db(conn, TASK_ID)
            insert_segmentation_results_db(conn, TASK_ID, all_polygons, user_id, status)

            # 无需手动清理 output_dir，因为 TemporaryDirectory 会自动删除
            if model_scope_str:
                os.remove(cropped_image_path)
                print(f"已删除临时文件: {cropped_image_path}")

            model = None
            torch.cuda.empty_cache()

            # 将映射规则保存到数据库
            type_id_to_name = match_typeid_to_name(conn, table_name="type")
            if not type_id_to_name:
                print("无法获取 type_id 到 type_name 的映射，跳过保存映射规则。")
            else:
                # 构建自然语言的映射描述
                mapping_parts = [
                    f"通道 {class_id} 对应类别 {type_id_to_name.get(type_id, '未知类别')}"
                    for type_id, class_id in type_id_to_class_id.items()
                ]
                mapping_data = "; ".join(mapping_parts)
            with rasterio.open(cropped_image_path if model_scope_str else IMAGE_PATH) as src:
                input_num = src.count  # 输入通道数
            save_model_to_db(
                conn=conn,
                model_name=model_name,
                user_id=user_id,
                mapping=mapping_data,
                model_path=os.path.join(detection_output_dir, f"{MODEL_TYPE}/weights/best.pt"),
                input_num=input_num,
                output_num=len(type_id_to_class_id),
            )

    # output_dir 及其内容会在 with 块结束后自动删除
    # elif MODEL_TYPE in ["yolo"]:
    #     # 裁剪影像
    #     cropped_image_path, crop_transform = crop_image_by_scope(IMAGE_PATH, model_scope_str)

    #     # 创建 YOLO 数据集
    #     output_dir = os.path.join(os.getcwd(), "yolo_dataset")
    #     images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels = create_yolo_dataset(
    #         labels_data, cropped_image_path, output_dir, model_scope_str
    #     )

    #     class_id_to_type_id = {v: k for k, v in type_id_to_class_id.items()}
    #     print(f"type_id 到 class_id 映射: {type_id_to_class_id}")
    #     print(f"class_id 到 type_id 映射: {class_id_to_type_id}")
    #     mapping_path = os.path.join(detection_output_dir, "mapping.json")
    #     with open(mapping_path, 'w') as f:
    #         json.dump({
    #             'type_id_to_class_id': type_id_to_class_id,
    #             'class_id_to_type_id': {str(v): k for k, v in type_id_to_class_id.items()}
    #         }, f)
    #     print(f"映射规则已保存至: {mapping_path}")

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

    #     # 训练 YOLO 模型
    #     model = YOLO("yolo11m-obb.pt")
    #     train_results = model.train(
    #         data=data_yaml_path,
    #         epochs=NUM_EPOCHS,
    #         imgsz=IMG_SIZE,
    #         device=device,
    #         project=detection_output_dir,
    #         name=f"{MODEL_TYPE}",
    #         save=True
    #     )

    #     # 推理
    #     inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
    #     results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=IMG_SIZE, save=True, save_txt=True)

    #     # 使用裁剪后的变换或原始变换
    #     transform = crop_transform if crop_transform else rasterio.open(IMAGE_PATH).transform

    #     # 处理检测结果
    #     detection_polygons, detection_boxes, detection_labels = process_yolo_results(
    #         results, transform, TASK_ID, user_id, status, conn, class_id_to_type_id, inference_output_path, cropped_image_path
    #     )

    #     # 将原始标注转换为 Shapely 多边形
    #     original_polygons = []
    #     for _, geom_str, _, *_ in labels_data:
    #         coords_str_list = geom_str.split(',')
    #         coords_list = [(float(coords_str_list[i].strip()), float(coords_str_list[i+1].strip())) 
    #                     for i in range(0, len(coords_str_list), 2)]
    #         original_polygons.append(Polygon(coords_list))

    #     # 过滤重叠的原始标注
    #     def filter_original_labels(original_polygons, predicted_polygons, distance_threshold=15):

    #         filtered_original = []
    #         # Flatten predicted_polygons into a list of Polygon objects and create MultiPolygon
    #         all_predicted = [poly for polys in predicted_polygons.values() for poly in polys]
    #         predicted_multipoly = MultiPolygon(all_predicted) if all_predicted else MultiPolygon()
            
    #         for orig_poly in original_polygons:
    #             orig_centroid = orig_poly.centroid
    #             keep = True
    #             # Iterate over individual Polygon objects in MultiPolygon using .geoms
    #             for pred_poly in predicted_multipoly.geoms:
    #                 pred_centroid = pred_poly.centroid
    #                 if orig_centroid.distance(pred_centroid) < distance_threshold:
    #                     keep = False
    #                     break
    #             if keep:
    #                 filtered_original.append(orig_poly)
    #         return filtered_original

    #     filtered_original_polygons = filter_original_labels(original_polygons, detection_polygons,distance_threshold=float(sys.argv[7]))

    #     # 合并过滤后的原始标注和预测标注
    #     all_polygons = {type_id: filtered_original_polygons + detection_polygons.get(type_id, []) 
    #                     for type_id in type_ids}

    #     # 可视化
    #     # if detection_boxes:
    #     #     draw_boxes_on_image(jpeg_path, detection_boxes, detection_labels, inference_output_path, color=(255, 0, 0))
    #     # else:
    #     #     shutil.copy(jpeg_path, inference_output_path)
    #     #     print("无检测结果，保存原始图像")

    #     # 写入数据库
    #     # delete_existing_results_db(conn, TASK_ID)
    #     insert_segmentation_results_db(conn, TASK_ID, all_polygons, user_id, status)

    #     # 清理临时文件
    #     cleanup_training_files(output_dir)
    #     if model_scope_str:
    #         os.remove(cropped_image_path)
    #         print(f"已删除临时文件: {cropped_image_path}")
    
    # elif MODEL_TYPE in ["yolo"]:
    #     # 裁剪影像
    #     cropped_image_path, crop_transform = crop_image_by_scope(IMAGE_PATH, model_scope_str)

    #     # 创建 YOLO 数据集并获取原始标注框
    #     output_dir = os.path.join(os.getcwd(), "yolo_dataset")
    #     images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels = create_yolo_dataset(
    #         labels_data, cropped_image_path, output_dir
    #     )

    #     class_id_to_type_id = {v: k for k, v in type_id_to_class_id.items()}
    #     print(f"type_id 到 class_id 映射: {type_id_to_class_id}")
    #     print(f"class_id 到 type_id 映射: {class_id_to_type_id}")
    #     # 保存映射规则到 JSON 文件
    #     mapping_path = os.path.join(detection_output_dir, "mapping.json")
    #     with open(mapping_path, 'w') as f:
    #         json.dump({
    #             'type_id_to_class_id': type_id_to_class_id,
    #             'class_id_to_type_id': {str(v): k for k, v in type_id_to_class_id.items()}
    #         }, f)
    #     print(f"映射规则已保存至: {mapping_path}")

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

    #     # 初始化 YOLO 模型
    #     model = YOLO("yolo11m-obb.pt")

    #     # 训练 YOLO 模型
    #     train_results = model.train(
    #         data=data_yaml_path,
    #         epochs=NUM_EPOCHS,
    #         imgsz=IMG_SIZE,
    #         device=device,
    #         project=detection_output_dir,
    #         name=f"{MODEL_TYPE}",
    #         save=True
    #     )

    #     # 使用裁剪后的变换信息
    #     with rasterio.open(cropped_image_path) as src:
    #         crop_transform = src.transform

    #     # 进行目标检测
    #     inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
    #     results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=IMG_SIZE, save=True, save_txt=True)

    #     # 处理 YOLO 检测结果
    #     detection_polygons, detection_boxes, detection_labels = process_yolo_results(
    #         results, crop_transform, TASK_ID, user_id, status, conn, class_id_to_type_id, inference_output_path, cropped_image_path
    #     )

    #     # 可视化推理结果
    #     if detection_boxes:
    #         draw_boxes_on_image(jpeg_path, detection_boxes, detection_labels, inference_output_path, color=(255, 0, 0))
    #     else:
    #         shutil.copy(jpeg_path, inference_output_path)
    #         print("无检测结果，保存原始图像作为推理结果可视化")

    #     # 删除数据库中旧的检测结果
    #     # delete_existing_results_db(conn, TASK_ID)

    #     # 将新结果写入数据库
    #     insert_segmentation_results_db(conn, TASK_ID, detection_polygons, user_id, status)

    #     # 清理临时文件
    #     # cleanup_training_files(output_dir)
    #     # if model_scope_str:
    #     #     os.remove(cropped_image_path)
    #     #     os.remove(jpeg_path)
    #     #     print(f"已删除临时文件: {cropped_image_path}, {jpeg_path}")

        '''原始版本不包括作用范围'''
        # # 创建 YOLO 数据集并获取原始标注框
        # output_dir = os.path.join(os.getcwd(), "yolo_dataset")
        # images_dir, labels_dir, type_id_to_class_id, jpeg_path, original_boxes, original_labels = create_yolo_dataset(labels_data, IMAGE_PATH, output_dir)

        # class_id_to_type_id = {v: k for k, v in type_id_to_class_id.items()}
        # print(f"type_id 到 class_id 映射: {type_id_to_class_id}")
        # print(f"class_id 到 type_id 映射: {class_id_to_type_id}")
        # # 保存映射规则到 JSON 文件
        # mapping_path = os.path.join(detection_output_dir, "mapping.json")
        # with open(mapping_path, 'w') as f:
        #     json.dump({
        #         'type_id_to_class_id': type_id_to_class_id,
        #         'class_id_to_type_id': {str(v): k for k, v in type_id_to_class_id.items()}  # JSON 键必须为字符串
        #     }, f)
        # print(f"映射规则已保存至: {mapping_path}")

        # os.makedirs(os.path.join(images_dir, "train"), exist_ok=True)
        # os.makedirs(os.path.join(images_dir, "val"), exist_ok=True)
        # os.makedirs(os.path.join(labels_dir, "train"), exist_ok=True)
        # os.makedirs(os.path.join(labels_dir, "val"), exist_ok=True)

        # image_name = os.path.basename(jpeg_path)
        # label_name = image_name.replace(".jpg", ".txt")
        # for split in ["train", "val"]:
        #     shutil.copy(os.path.join(images_dir, image_name),
        #                 os.path.join(images_dir, split, image_name))
        #     shutil.copy(os.path.join(labels_dir, label_name),
        #                 os.path.join(labels_dir, split, label_name))

        # data_yaml_path = create_yolo_data_yaml(output_dir, images_dir, labels_dir, type_ids_from_db)

        # # 可视化原始标注框
        # # original_output_path = os.path.join(output_dir, "original_with_boxes.jpg")
        # # draw_boxes_on_image(jpeg_path, original_boxes, original_labels, original_output_path, color=(0, 255, 0))

        # # 初始化 YOLO 模型 (改为 yolo11n-obb)
        # model = YOLO("yolo11m-obb.pt")

        # # 训练 YOLO 模型
        # train_results = model.train(
        #     data=data_yaml_path,
        #     epochs=NUM_EPOCHS,
        #     imgsz=IMG_SIZE,
        #     device=device,
        #     project=detection_output_dir,    # 项目目录名设置为 model_save_dir (trained_models)
        #     name=f"{MODEL_TYPE}",          # 运行名称(子目录)设置为 task_id
        #     save=True                      # 启用保存
        # )

        # with rasterio.open(IMAGE_PATH) as src:
        #     original_transform = src.transform

        # # 进行目标检测
        # inference_output_path = os.path.join(output_dir, "inference_with_boxes.jpg")
        # results = model(jpeg_path, conf=CONF_THRESHOLD, imgsz=1024, save=True, save_txt=True)

        # # 处理 YOLO 检测结果
        # detection_polygons, detection_boxes, detection_labels = process_yolo_results(
        #     results, original_transform, TASK_ID, user_id, status, conn, class_id_to_type_id, inference_output_path,IMAGE_PATH
        # )

        # # 可视化推理结果
        # if detection_boxes:
        #     draw_boxes_on_image(jpeg_path, detection_boxes, detection_labels, inference_output_path, color=(255, 0, 0))
        # else:
        #     shutil.copy(jpeg_path, inference_output_path)
        #     print("无检测结果，保存原始图像作为推理结果可视化")

        # # 删除数据库中旧的检测结果
        # delete_existing_results_db(conn, TASK_ID)

        # # 将新结果写入数据库
        # insert_segmentation_results_db(conn, TASK_ID, detection_polygons, user_id, status)

        # # 写入数据库后，删除训练文件
        # cleanup_training_files(output_dir)
        # # 清理临时文件
        # if model_scope:
        #     # os.remove(cropped_image_path)
        #     os.remove(jpeg_path)
        #     # print(f"已删除临时文件: {cropped_image_path}, {jpeg_path}")
    
    # elif MODEL_TYPE in ["sam"]:
    #     # 创建临时文件目录
    #     with tempfile.TemporaryDirectory() as temp_dir:
    #         temp_out = os.path.join(temp_dir, "sam.tif")
            
    #         # 不再使用 crop_tiff_by_polygon 方法
    #         # 改为使用 shapely 的 buffer、coverage_union_all 和 envelope 方法
            
    #         # 收集所有类型的点坐标
    #         all_points = []
    #         for type_id in type_ids:
    #             points = generate_point_coordinates_sam(labels_data, type_id)
    #             if points:
    #                 all_points.extend(points)
            
    #         # 如果有点坐标，则计算裁剪范围
    #         if all_points and model_scope_str:

                
    #             # 创建点的几何对象并添加缓冲区
    #             buffered_points = [buffer(Point(x, y), 0.0001) for x, y in all_points]
                
    #             # 合并所有缓冲区
    #             if len(buffered_points) > 1:
    #                 merged_buffer = coverage_union_all(buffered_points)
    #             else:
    #                 merged_buffer = buffered_points[0]
                
    #             # 获取最小边界框
    #             bbox = envelope(merged_buffer)
                
    #             # 获取边界框的坐标
    #             minx, miny, maxx, maxy = bbox.bounds
                
    #             # 打开原始影像
    #             with rasterio.open(IMAGE_PATH) as src:
    #                 # 将坐标从 EPSG:4326 转换为影像的坐标系统
    #                 src_crs = src.crs
    #                 dst_crs = "EPSG:4326"
    #                 minx, miny, maxx, maxy = transform_bounds(dst_crs, src_crs, minx, miny, maxx, maxy)
                    
    #                 # 计算窗口
    #                 window = from_bounds(minx, miny, maxx, maxy, src.transform)
                    
    #                 # 读取窗口内的数据
    #                 data = src.read(window=window)
                    
    #                 # 创建裁剪后的影像元数据
    #                 out_meta = src.meta.copy()
    #                 out_transform = rasterio.windows.transform(window, src.transform)
    #                 out_meta.update({
    #                     "height": window.height,
    #                     "width": window.width,
    #                     "transform": out_transform
    #                 })
                    
    #                 # 保存裁剪后的影像
    #                 with rasterio.open(temp_out, "w", **out_meta) as dst:
    #                     dst.write(data)
                
    #             print(f"已根据点坐标缓冲区裁剪影像到: {temp_out}")
    #         else:
    #             # 如果没有点坐标或不需要裁剪，直接使用原始影像
    #             temp_out = IMAGE_PATH
    #             print("使用原始影像进行处理")

    #         sam = copy.deepcopy(global_sam)
    #         sam.set_image(temp_out)

    #         # 用于存储所有 type_id 的分割结果
    #         all_segmentation_polygons = {}

    #         # 删除绘制的点数据
    #         delete_point_results_db(conn, TASK_ID)

    #         # 处理每个 type_id
    #         for type_id in type_ids:
    #             print(f"处理 type_id: {type_id}")
    #             point_4326 = generate_point_coordinates_sam(labels_data, type_id)
    #             if not point_4326:
    #                 print(f"type_id {type_id} 没有找到多边形，跳过。")
    #                 continue

    #             # 创建临时掩码文件
    #             with tempfile.NamedTemporaryFile(suffix='.tif', dir=temp_dir, delete=False) as mask_file:
    #                 mask_path = mask_file.name
                    
    #                 # 创建点标签数组，全部设置为1（表示前景）
    #                 point_labels = np.ones(len(point_4326), dtype=int)
                    
    #                 # 使用 SAM 进行预测，添加 point_labels 参数
    #                 sam.predict_by_points(
    #                     point_coords_batch=point_4326, 
    #                     point_labels=point_labels,  # 添加点标签参数
    #                     point_crs="EPSG:4326", 
    #                     output=mask_path, 
    #                     dtype="uint8"
    #                 )
    #                 # global_sam.predict(point_coords=point_4326, point_labels=1, point_crs="EPSG:4326", output=mask_path)
    #                 # print("2")
    #                 # 读取掩码
    #                 with rasterio.open(mask_path) as mask_src:
    #                     mask = mask_src.read(1)  # 假设掩码是单波段的

    #                 # 应用后处理
    #                 processed_mask = post_process_mask_sam(
    #                     mask,
    #                     min_object_size=int(argv[5]),
    #                     hole_size_threshold=int(argv[6]),
    #                     boundary_smoothing=int(argv[7])
    #                 )

    #                 # 保存处理后的掩码回 mask_path
    #                 with rasterio.open(mask_path, 'w', **mask_src.meta) as dst:
    #                     dst.write(processed_mask, 1)

    #             # 矢量化掩膜
    #             with rasterio.open(temp_out) as src:
    #                 transform = src.transform  # EPSG:3857 变换
    #             with rasterio.open(mask_path) as mask_src:
    #                 mask = mask_src.read(1)
    #             segmentation_polygons = identify_holes_and_split_SAM(mask, transform, type_id)

    #             # 收集分割结果
    #             if segmentation_polygons:
    #                 all_segmentation_polygons.update(segmentation_polygons)
    #             else:
    #                 print(f"type_id {type_id} 未生成有效多边形。")

    #             # 删除临时掩膜文件
    #             os.remove(mask_path)
    #             print(f"已删除 {mask_path}")

    #         # 将所有分割结果写入数据库
    #         if all_segmentation_polygons:
    #             insert_segmentation_results_db(conn, TASK_ID, all_segmentation_polygons, user_id, status)
    #         else:
    #             print("没有生成任何分割多边形，未写入数据库。")

    #         # 清理资源
    #         sam = None
    #         torch.cuda.empty_cache()


    # temp_dir 及其中的所有文件会在 with 块结束后自动删除
    # elif MODEL_TYPE in ["sam"]:
    #     from samgeo import SamGeo2
    #     temp_out = "/home/change/labelcode/labelMark/temp_inference/sam.tif"
        
    #     result = crop_tiff_by_polygon(IMAGE_PATH, temp_out, model_scope_str)
    #     if result:
    #         pass
    #     else:
    #         temp_out = IMAGE_PATH

    #     sam = SamGeo2(
    #         model_id="sam2-hiera-tiny",
    #         automatic=False,
    #     )
    #     sam.set_image(temp_out)

    #     # 用于存储所有 type_id 的分割结果
    #     all_segmentation_polygons = {}

    #     # 在循环开始前删除原有数据
    #     delete_point_results_db(conn, TASK_ID)

    #     # 处理每个 type_id
    #     for type_id in type_ids:
    #         print(f"处理 type_id: {type_id}")
    #         point_4326= generate_point_coordinates_sam(labels_data, type_id)
    #         if not point_4326:
    #             print(f"type_id {type_id} 没有找到多边形，跳过。")
    #             continue

    #         mask_path = f"mask_{type_id}.tif"
    #         # 使用 SAM 进行预测
    #         sam.predict_by_points(point_coords_batch=point_4326, point_crs="EPSG:4326", output=mask_path, dtype="uint8")
    #         # sam.predict(point_coords=point_4326, point_labels=1, point_crs="EPSG:4326", output=mask_path)

    #         # 读取掩码
    #         with rasterio.open(mask_path) as mask_src:
    #             mask = mask_src.read(1)  # 假设掩码是单波段的

    #         # 应用后处理
    #         # processed_mask = post_process_mask_sam(mask, min_object_size=500, hole_size_threshold=500, boundary_smoothing=2)
    #         processed_mask = post_process_mask_sam(mask,min_object_size=int(sys.argv[5]), hole_size_threshold=int(sys.argv[6]),boundary_smoothing=int(sys.argv[7]))

    #         # 保存处理后的掩码回 mask_path
    #         with rasterio.open(mask_path, 'w', **mask_src.meta) as dst:
    #             dst.write(processed_mask, 1)

    #         # 矢量化掩膜
    #         with rasterio.open(temp_out) as src:
    #             transform = src.transform  # EPSG:3857 变换
    #         with rasterio.open(mask_path) as mask_src:
    #             mask = mask_src.read(1)
    #         segmentation_polygons = identify_holes_and_split_SAM(mask, transform, type_id)

    #         # 收集分割结果
    #         if segmentation_polygons:
    #             all_segmentation_polygons.update(segmentation_polygons)
    #             # all_segmentation_polygons.update(others)
    #         else:
    #             print(f"type_id {type_id} 未生成有效多边形。")

    #         # 删除临时掩膜文件
    #         os.remove(mask_path)
    #         print(f"已删除 {mask_path}")

    #     # 将所有分割结果写入数据库
    #     if all_segmentation_polygons:
    #         insert_segmentation_results_db(conn, TASK_ID, all_segmentation_polygons, user_id, status)
    #         os.remove(temp_out)
    #     else:
    #         print("没有生成任何分割多边形，未写入数据库。")

    else:
        print(f"未知的模型类型: {MODEL_TYPE}")
        conn.close()
        return

    # 关闭数据库连接
    conn.close()
    print("任务完成!")
