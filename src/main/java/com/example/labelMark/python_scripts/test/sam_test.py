import os
import psycopg2
import rasterio
import numpy as np
from shapely.geometry import Polygon
import cv2
import rtree.index
from samgeo import SamGeo,SamGeo2
from pyproj import Transformer

# Database connection info (replace with your actual values)
DB_HOST = "localhost"
DB_NAME = "label"
DB_USER = "postgres"
DB_PASSWORD = "123456"
DB_PORT = "5432"
TABLE_NAME = "mark"
TABLE_NAME2 = "task"

# Coordinate transformation setup
TRANSFORMER_3857_TO_4326 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
TRANSFORMER_4326_TO_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

# -------------------- Database Operation Functions --------------------
def connect_db():
    """Connect to PostgreSQL database."""
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
    """Fetch label data for a given task_id from the database."""
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
    """Delete existing data for a given task_id from the database."""
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
    """Write segmentation results to the database using original coordinate string format."""
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

# -------------------- Bounding Box Generation Function --------------------
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

# -------------------- Hole Handling Functions --------------------
def connect_multiple_holes(exterior_coords, interior_coords_list, max_distance=10.0):
    current_exterior = exterior_coords[:]
    
    exterior_index = rtree.index.Index()
    for idx, (x, y) in enumerate(current_exterior):
        exterior_index.insert(idx, (x, y, x, y))
    
    for idx, interior_coords in enumerate(interior_coords_list):
        min_dist = float('inf')
        best_exterior_idx = 0
        best_interior_idx = 0
        
        for i, (ix, iy) in enumerate(interior_coords):
            nearest_idx = list(exterior_index.nearest((ix, iy, ix, iy), 1))[0]
            ex, ey = current_exterior[nearest_idx]
            dist = ((ix - ex) ** 2 + (iy - ey) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                best_exterior_idx = nearest_idx
                best_interior_idx = i
        
        new_exterior = []
        new_exterior.extend(current_exterior[:best_exterior_idx + 1])
        reordered_interior = interior_coords[best_interior_idx:] + interior_coords[:best_interior_idx]
        new_exterior.extend(reordered_interior)
        new_exterior.append(reordered_interior[0])
        new_exterior.extend(current_exterior[best_exterior_idx:])
        
        current_exterior = new_exterior
        exterior_index = rtree.index.Index()
        for j, (x, y) in enumerate(current_exterior):
            exterior_index.insert(j, (x, y, x, y))
    
    return current_exterior

def identify_holes_and_split(mask, transform, type_id, min_area=30):
    """Convert mask to polygons, handling holes with connect_multiple_holes."""
    polygons = {}
    class_mask = mask.astype(np.uint8)
    contours, hierarchy = cv2.findContours(class_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None or len(contours) == 0:
        return polygons

    class_polygons = []
    i = 0
    while i < len(contours):
        if len(contours[i]) < 3 or cv2.contourArea(contours[i]) < min_area:
            i += 1
            continue
        if hierarchy[0][i][3] == -1:
            exterior_coords = [transform * (point[0][0], point[0][1]) for point in contours[i]]
            exterior_coords = [(x, y) for x, y in exterior_coords]
            interior_contours = []
            hole_idx = hierarchy[0][i][2]
            while hole_idx != -1:
                if len(contours[hole_idx]) >= 3 and cv2.contourArea(contours[hole_idx]) >= min_area:
                    interior_coords = [transform * (point[0][0], point[0][1]) for point in contours[hole_idx]]
                    interior_coords = [(x, y) for x, y in interior_coords]
                    interior_contours.append(interior_coords)
                hole_idx = hierarchy[0][hole_idx][0]
            if interior_contours:
                final_coords = connect_multiple_holes(exterior_coords, interior_contours, max_distance=1000.0)
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

# -------------------- Main Function --------------------
def main():
    TASK_ID = 131
    IMAGE_PATH = "/home/change/labelcode/labelMark/src/main/java/com/example/labelMark/resource/output/airs.tif"

    conn = connect_db()
    if conn is None:
        print("无法连接到数据库，程序退出。")
        return

    original_row_data = fetch_labels_from_db(conn, TASK_ID)
    if not original_row_data:
        print(f"task_id {TASK_ID} 没有找到标签数据，请检查数据库。")
        conn.close()
        return

    user_ids = set(row[3] for row in original_row_data)
    if len(user_ids) > 1:
        print(f"警告: task_id {TASK_ID} 包含多个 user_id: {user_ids}，使用第一个")
    user_id = original_row_data[0][3]
    status = original_row_data[0][5]

    type_ids = set(row[2] for row in original_row_data)

    # sam = SamGeo(
    #     model_type="vit_h",
    #     automatic=False,
    #     sam_kwargs=None,
    # )
    sam = SamGeo2(
    model_id="sam2-hiera-large",
    automatic=False,
    )
    sam.set_image(IMAGE_PATH)
    delete_existing_results_db(conn, TASK_ID)

    for type_id in type_ids:
        print(f"处理 type_id: {type_id}")
        boxes_4326 = generate_bounding_boxes(original_row_data, type_id)
        if not boxes_4326:
            print(f"type_id {type_id} 没有找到多边形，跳过。")
            continue

        mask_path = f"mask_{type_id}.tif"
        # SAM prediction using EPSG:4326 bounding boxes
        sam.predict(boxes=boxes_4326, point_crs="EPSG:4326", output=mask_path, dtype="uint8")

        # Vectorize in EPSG:3857 (using the transform from the original image)
        with rasterio.open(IMAGE_PATH) as src:
            transform = src.transform  # EPSG:3857 transform
        with rasterio.open(mask_path) as mask_src:
            mask = mask_src.read(1)
        segmentation_polygons = identify_holes_and_split(mask, transform, type_id, min_area=30)

        if segmentation_polygons:
            insert_segmentation_results_db(conn, TASK_ID, segmentation_polygons, user_id, status)
        else:
            print(f"type_id {type_id} 未生成有效多边形。")

        os.remove(mask_path)
        print(f"已删除 {mask_path}")

    conn.close()
    print("任务完成!")

if __name__ == "__main__":
    main()