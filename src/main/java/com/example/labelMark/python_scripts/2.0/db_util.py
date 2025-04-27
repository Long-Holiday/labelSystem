import psycopg2

class DB:
    def __init__(self, host, dbname, user, password, port):
        self.host = host
        self.dbname = dbname
        self.user = user
        self.password = password
        self.port = port

    def connect_db(self):
        try:
            conn = psycopg2.connect(host=self.host, database=self.dbname, user=self.user,
                                     password=self.password, port=self.port)
            return conn
        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}")
            return None
        
    def fetch_map_server_from_db(self, conn, task_id, TABLE_NAME2="task"):
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
        
    def fetch_typeid_from_db(self, conn, task_id, table_name="task_accepted"):
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

    def fetch_labels_from_db(self, conn, task_id, table_name="mark"):
        if conn is None:
            return []
        try:
            cursor = conn.cursor()
            query = f"SELECT id, geom, type_id, user_id, task_id, status FROM {table_name} WHERE task_id = %s"
            cursor.execute(query, (task_id,))
            labels_data = cursor.fetchall()
            cursor.close()
            return labels_data
        except psycopg2.Error as e:
            print(f"Error fetching labels from database: {e}")
            return []

    def delete_existing_results_db(self, conn, task_id, table_name="mark"):
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

    def delete_point_results_db(self, conn, task_id, table_name="mark"):
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

    def insert_segmentation_results_db(self, conn, task_id, segmentation_polygons, user_id, status, table_name="mark"):
        if conn is None:
            return
        cursor = conn.cursor()
        insert_query = f"INSERT INTO {table_name} (geom, type_id, user_id, task_id, status) VALUES %s"
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
