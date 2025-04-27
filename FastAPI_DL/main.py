import copy
import json
import os
import tempfile
import numpy as np
import rasterio
from shapely import Point, buffer, coverage_union_all, envelope
import torch
import torch.multiprocessing as mp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from utils import connect_db, delete_point_results_db, fetch_labels_from_db, fetch_map_server_from_db, generate_point_coordinates_sam, identify_holes_and_split_SAM, post_process_mask_sam
from train import train_function, router
from update_label import insert_segmentation_results_db, update_label_function
from inference import inference
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

# 在创建任何多进程对象之前设置启动方式
mp.set_start_method('spawn', force=True)

app = FastAPI(debug=True)  # 创建 FastAPI 实例
app.include_router(router)  # 挂载路由
global_sam = None  # 全局变量，用于存储 SamGeo 实例

# 创建任务队列（仅用于 assist_function）
assist_queue = mp.Queue()  # 用于 assist_function 的任务队列

# 定义处理 assist_function 的函数
def process_assist(queue):
    """处理 assist_function 请求的任务进程"""
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA不可用，请检查GPU和驱动")
    while True:
        task = queue.get()  # 从队列中获取任务
        if task is None:  # 如果收到 None，则退出循环
            break
        # 使用独立的 CUDA 流执行任务
        with torch.cuda.stream(torch.cuda.Stream()):
            train_function(task)

# 定义 inference_function 的独立进程执行函数
def run_inference(argv):
    """在独立进程中执行 inference_function"""
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA不可用，请检查GPU和驱动")
    with torch.cuda.stream(torch.cuda.Stream()):
        inference(argv)

# 启动事件：启动 assist_function 的进程
@app.on_event("startup")
async def startup_event():
    # 启动 assist_function 的进程
    global assist_process
    assist_process = mp.Process(target=process_assist, args=(assist_queue,))
    assist_process.start()
    print("assist_function 任务处理进程已启动")

    from samgeo import SamGeo2
    # from samgeo import SamGeo
    global global_sam
    if global_sam is None:
        global_sam = SamGeo2(  # 延迟实例化到启动事件
            model_id="sam2-hiera-base-plus",
            # model_id="sam2-hiera-small",
            automatic=False,
            device="cuda",
        )
        # global_sam = SamGeo(  # 延迟实例化到启动事件
        #     model_id="vit_b",
        #     automatic=False,
        #     device="cuda",
        # )
    print("SamGeo 已实例化")

# 关闭事件：关闭 assist_function 的进程
@app.on_event("shutdown")
async def shutdown_event():
    # 向 assist_queue 发送 None 以停止进程
    assist_queue.put(None)
    
    # 等待进程结束
    assist_process.join()
    print("assist_function 任务处理进程已关闭")

# 定义请求体模型
class AssistFunctionRequest(BaseModel):
    taskid: str
    mapfile_path: str
    functionName: str
    assistInput: str = ""
    modelName: str = ""
    param1: str = ""
    param2: str = ""
    param3: str = ""
    param4: str = ""
    user_id: str = None
    modelScopeStr: str = ""
    tasktype: str = ""  # 区分任务类型

class InferenceFunctionRequest(BaseModel):
    taskid: str
    mapfile_path: str
    user_id: str
    model: str = ""
    param1: str = ""
    param2: str = ""
    param3: str = ""
    param4: str = ""
    param5: str = ""
    param6: str = ""
    param7: str = ""
    param8: str = ""
    modelScopeStr: str = ""

class UpdateLabelRequest(BaseModel):
    taskid: str
    mapfile_path: str

@app.post("/assistFunction")
async def assist_function(request: AssistFunctionRequest):
    """处理 assist_function 请求，将任务加入队列"""
    try:
        # 获取参数并构造任务参数列表
        taskid = request.taskid
        mapfile_path = request.mapfile_path
        function_name = request.functionName
        assist_input = request.assistInput
        model_name = request.modelName
        param1 = request.param1
        param2 = request.param2
        param3 = request.param3
        param4 = request.param4
        user_id = request.user_id
        model_scope_str = request.modelScopeStr
        task_type = request.tasktype

        argv = ["", taskid, mapfile_path, function_name, assist_input, param1, param2,
                 param3, param4, user_id, model_scope_str, model_name, task_type]
        print(f"收到 assist_function 请求: {argv}")

        # 将任务放入 assist_queue
        assist_queue.put(argv)

        return {"code": 200, "message": "任务已加入队列"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用辅助功能失败: {str(e)}")

@app.post("/inferenceFunction")
async def inference_function(request: InferenceFunctionRequest):
    """处理 inference_function 请求，在独立进程中执行并等待完成"""
    try:
        # 获取参数并构造任务参数列表
        taskid = request.taskid
        mapfile_path = request.mapfile_path
        user_id = request.user_id
        model = request.model
        param1 = request.param1
        param2 = request.param2
        param3 = request.param3
        param4 = request.param4
        param5 = request.param5
        param6 = request.param6
        param7 = request.param7
        param8 = request.param8
        modelScopeStr = request.modelScopeStr

        class_mappping = {
            0: param5,
            1: param6,
            2: param7,
            3: param8
        }

        argv = ["", taskid, mapfile_path, user_id, model, param1, param2, param3, param4, modelScopeStr,class_mappping]
        print(f"收到 inference_function 请求: {argv}")

        # 直接在主进程中调用推理函数
        if request.model == "SAM":
            inference_sam(argv)
        else:
            run_inference(argv)
        return {"code": 200, "message": "Inference completed"}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/update_label")
async def update_label(request: UpdateLabelRequest):
    """处理 update_label 请求，在独立进程中执行并等待完成"""
    try:
        # 获取参数并构造任务参数列表
        taskid = request.taskid
        mapfile_path = request.mapfile_path

        argv = ["", taskid, mapfile_path]
        print(f"收到 update_label 请求: {argv}")

        update_label_function(argv)

        return {"code": 200, "message": "更新任务已完成"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新样本失败: {str(e)}")
    
def inference_sam(argv):
    # 连接数据库
    # conn = db_conn
    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return
    TASK_ID = int(argv[1])
    MAPFILE_PATH = argv[2]

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

    # 获取所有 type_ids
    type_ids = set(row[2] for row in labels_data)

    # 创建临时文件目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_out = os.path.join(temp_dir, "sam.tif")
        
        # 不再使用 crop_tiff_by_polygon 方法
        # 改为使用 shapely 的 buffer、coverage_union_all 和 envelope 方法
        
        # 收集所有类型的点坐标
        all_points = []
        for type_id in type_ids:
            points = generate_point_coordinates_sam(labels_data, type_id)
            if points:
                all_points.extend(points)
        
        # 如果有点坐标，则计算裁剪范围
        if all_points:

            
            # 创建点的几何对象并添加缓冲区
            buffered_points = [buffer(Point(x, y), 0.0001) for x, y in all_points]
            
            # 合并所有缓冲区
            if len(buffered_points) > 1:
                merged_buffer = coverage_union_all(buffered_points)
            else:
                merged_buffer = buffered_points[0]
            
            # 获取最小边界框
            bbox = envelope(merged_buffer)
            
            # 获取边界框的坐标
            minx, miny, maxx, maxy = bbox.bounds
            
            # 打开原始影像
            with rasterio.open(IMAGE_PATH) as src:
                # 将坐标从 EPSG:4326 转换为影像的坐标系统
                src_crs = src.crs
                dst_crs = "EPSG:4326"
                minx, miny, maxx, maxy = transform_bounds(dst_crs, src_crs, minx, miny, maxx, maxy)
                
                # 计算窗口
                window = from_bounds(minx, miny, maxx, maxy, src.transform)
                
                # 读取窗口内的数据
                data = src.read(window=window)
                
                # 创建裁剪后的影像元数据
                out_meta = src.meta.copy()
                out_transform = rasterio.windows.transform(window, src.transform)
                out_meta.update({
                    "height": window.height,
                    "width": window.width,
                    "transform": out_transform
                })
                
                # 保存裁剪后的影像
                with rasterio.open(temp_out, "w", **out_meta) as dst:
                    dst.write(data)
            
            print(f"已根据点坐标缓冲区裁剪影像到: {temp_out}")
        else:
            # 如果没有点坐标或不需要裁剪，直接使用原始影像
            temp_out = IMAGE_PATH
            print("使用原始影像进行处理")

        sam = copy.deepcopy(global_sam)
        sam.set_image(temp_out)

        # 用于存储所有 type_id 的分割结果
        all_segmentation_polygons = {}

        # 删除绘制的点数据
        delete_point_results_db(conn, TASK_ID)

        # 处理每个 type_id
        for type_id in type_ids:
            print(f"处理 type_id: {type_id}")
            point_4326 = generate_point_coordinates_sam(labels_data, type_id)
            if not point_4326:
                print(f"type_id {type_id} 没有找到多边形，跳过。")
                continue

            # 创建临时掩码文件
            with tempfile.NamedTemporaryFile(suffix='.tif', dir=temp_dir, delete=False) as mask_file:
                mask_path = mask_file.name
                
                # 创建点标签数组，全部设置为1（表示前景）
                point_labels = np.ones(len(point_4326), dtype=int)
                
                # 使用 SAM 进行预测，添加 point_labels 参数
                sam.predict_by_points(
                    point_coords_batch=point_4326, 
                    point_labels=point_labels,  # 添加点标签参数
                    point_crs="EPSG:4326", 
                    output=mask_path, 
                    dtype="uint8"
                )
                # global_sam.predict(point_coords=point_4326, point_labels=1, point_crs="EPSG:4326", output=mask_path)
                # print("2")
                # 读取掩码
                with rasterio.open(mask_path) as mask_src:
                    mask = mask_src.read(1)  # 假设掩码是单波段的

                # 应用后处理
                processed_mask = post_process_mask_sam(
                    mask,
                    min_object_size=int(argv[5]),
                    hole_size_threshold=int(argv[6]),
                    boundary_smoothing=int(argv[7])
                )

                # 保存处理后的掩码回 mask_path
                with rasterio.open(mask_path, 'w', **mask_src.meta) as dst:
                    dst.write(processed_mask, 1)

            # 矢量化掩膜
            with rasterio.open(temp_out) as src:
                transform = src.transform  # EPSG:3857 变换
            with rasterio.open(mask_path) as mask_src:
                mask = mask_src.read(1)
            segmentation_polygons = identify_holes_and_split_SAM(mask, transform, type_id)

            # 收集分割结果
            if segmentation_polygons:
                all_segmentation_polygons.update(segmentation_polygons)
            else:
                print(f"type_id {type_id} 未生成有效多边形。")

            # 删除临时掩膜文件
            os.remove(mask_path)
            print(f"已删除 {mask_path}")

        # 将所有分割结果写入数据库
        if all_segmentation_polygons:
            insert_segmentation_results_db(conn, TASK_ID, all_segmentation_polygons, user_id, status)
        else:
            print("没有生成任何分割多边形，未写入数据库。")

        # 清理资源
        sam = None
        torch.cuda.empty_cache()
        conn.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)

# from fastapi import FastAPI, HTTPException
# import psycopg2
# from pydantic import BaseModel
# import subprocess
# import os

# from train import train_function, router
# from update_label import update_label_function
# from inference import inference

# app = FastAPI(debug=True)  # 创建 FastAPI 实例
# app.include_router(router)  # 挂载路由

# # 数据库连接信息
# DB_HOST = "localhost"
# DB_NAME = "label"
# DB_USER = "postgres"
# DB_PASSWORD = "123456"
# DB_PORT = "5432"

# # 全局数据库连接变量
# app.state.db_conn = None

# # 启动事件：建立数据库连接
# @app.on_event("startup")
# async def startup_event():
#     try:
#         app.state.db_conn = psycopg2.connect(
#             host=DB_HOST,
#             database=DB_NAME,
#             user=DB_USER,
#             password=DB_PASSWORD,
#             port=DB_PORT
#         )
#         print("数据库连接已成功建立")
#     except psycopg2.Error as e:
#         print(f"启动时无法连接到数据库: {e}")
#         app.state.db_conn = None

# # 关闭事件：断开数据库连接
# @app.on_event("shutdown")
# async def shutdown_event():
#     if app.state.db_conn is not None and not app.state.db_conn.closed:
#         app.state.db_conn.close()
#         print("数据库连接已关闭")
#     else:
#         print("无活动数据库连接需要关闭")

# # 定义请求体模型
# class AssistFunctionRequest(BaseModel):
#     taskid: str
#     mapfile_path: str
#     functionName: str
#     assistInput: str = ""
#     param1: str = ""
#     param2: str = ""
#     param3: str = ""
#     param4: str = ""
#     user_id: str = None
#     modelScopeStr: str = ""

# class InferenceFunctionRequest(BaseModel):
#     taskid: str
#     mapfile_path: str
#     user_id: str
#     model: str = ""
#     param1: str = ""
#     param2: str = ""
#     param3: str = ""
#     param4: str = ""
#     modelScopeStr: str = ""

# class UpdateLabelRequest(BaseModel):
#     taskid: str
#     mapfile_path: str

# @app.post("/assistFunction")
# async def assist_function(request: AssistFunctionRequest):
#     try:
#         # 获取参数
#         taskid = request.taskid
#         mapfile_path = request.mapfile_path
#         function_name = request.functionName
#         assist_input = request.assistInput
#         param1 = request.param1
#         param2 = request.param2
#         param3 = request.param3
#         param4 = request.param4
#         user_id = request.user_id
#         model_scope_str = request.modelScopeStr

#         argv = ["",taskid, mapfile_path, function_name, assist_input, param1, param2, param3, param4, user_id,
#                 model_scope_str]
#         print(argv)

#         train_function(argv,db_conn=app.state.db_conn)
#         # 这里可以实现你的辅助功能逻辑
#         # 例如：调用 Python 脚本或直接处理参数
#         # result = your_assist_function_logic(taskid, function_name, assist_input, user_id, parameters)

#         # 示例响应
#         return {"code": 200, "message": "成功调用辅助功能"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"调用辅助功能失败: {str(e)}")


# @app.post("/inferenceFunction")
# async def inference_function(request: InferenceFunctionRequest):
#     try:
#         # 获取参数
#         taskid = request.taskid
#         mapfile_path = request.mapfile_path
#         user_id = request.user_id
#         model = request.model
#         param1 = request.param1
#         param2 = request.param2
#         param3 = request.param3
#         param4 = request.param4
#         modelScopeStr = request.modelScopeStr

#         argv = ["",taskid,mapfile_path,user_id, model, param1, param2, param3, param4, modelScopeStr]
#         print(argv)
#         inference(argv,db_conn=app.state.db_conn)

#         # 这里可以实现你的模型推理逻辑
#         # 例如：调用 Python 脚本或直接处理参数
#         # result = your_inference_function_logic(taskid, user_id, model, parameters)

#         # 示例响应
#         return {"code": 200, "message": "模型推理成功"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"模型推理失败: {str(e)}")

# @app.post("/update_label")
# async def update_label(request: UpdateLabelRequest):
#     try:
#         # 获取参数
#         taskid = request.taskid
#         mapfile_path = request.mapfile_path

#         argv = ["",taskid,mapfile_path]
#         print(argv)

#         update_label_function(argv,db_conn=app.state.db_conn)

#         # 这里可以实现你的样本更新逻辑
#         # 例如：调用 Python 脚本或直接处理参数
#         # result = your_update_label_logic(taskid)

#         # 示例响应
#         return {"code": 200, "message": "成功更新样本"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"更新样本失败: {str(e)}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=5000)