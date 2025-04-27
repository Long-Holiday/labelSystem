import psycopg2 # 确保导入了 psycopg2 库

def fetch_model_from_db(conn, model_name, table_name="model"):
    """
    从数据库中根据模型名称查找单条模型记录。

    Args:
        conn: 数据库连接对象。
        model_name: 要查找的模型名称。
        table_name: 数据库表名，默认为 "model"。

    Returns:
        如果找到匹配的记录，则返回一个字典，键为列名，值为对应的字段值。
        如果未找到记录、conn为None或发生数据库错误，则返回一个空字典 {}。
    """
    # 处理连接为 None 的情况，返回空字典表示没有结果/无法查询
    if conn is None:
        # print("Database connection is None.") # 可以选择打印警告
        return {}

    try:
        # 使用 with 语句确保 cursor 被正确关闭
        with conn.cursor() as cursor:
            # 构建 SQL 查询语句
            query = f"SELECT model_name, user_id, model_des, path, input_num, output_num, status,model_type FROM {table_name} WHERE model_name= %s"
            
            # 执行查询，使用参数化查询防止SQL注入
            cursor.execute(query, (model_name,))

            # 获取列名。cursor.description 是一个元组的元组，每个内层元组描述一个列。
            # 第一个元素 [0] 是列名。
            if cursor.description is None:
                # 如果查询没有返回结果集（例如 DELETE/UPDATE），description 会是 None
                # 对于 SELECT 应该有 description，这里做个简单检查
                print("Warning: cursor.description is None after SELECT.")
                return {}

            column_names = [desc[0] for desc in cursor.description]

            # 获取单条结果。fetchone() 返回一个元组或 None。
            row_data = cursor.fetchone()

            # 检查是否找到了记录
            if row_data is None:
                # 没有找到匹配的记录，返回空字典
                return {}
            else:
                # 找到了记录，将列名和数据组合成字典
                # 使用 zip 将列名和数据值配对，然后转换为字典
                result_dict = dict(zip(column_names, row_data))
                return result_dict

    except psycopg2.Error as e:
        # 捕获 psycopg2 相关的数据库错误
        print(f"Error fetching model from database: {e}")
        # 发生错误时返回空字典
        return {}
    except Exception as e:
        # 捕获其他可能的异常
        print(f"An unexpected error occurred: {e}")
        return {}

# # 示例用法 (假设你有一个数据库连接 conn)
from utils import connect_db
conn = connect_db() # 获取数据库连接

if conn:
    model_info = fetch_model_from_db(conn, "test3")
    
    if model_info:
        print("找到模型信息:")
        print(model_info) # 打印字典
        print(f"Model Name: {model_info.get('model_name')}")
        print(f"User ID: {model_info.get('user_id')}")
    else:
        print(f"未找到模型 'MyTestModel' 或发生错误。")
        
    # conn.close() # 使用完连接后关闭
else:
    print("无法获取数据库连接。")