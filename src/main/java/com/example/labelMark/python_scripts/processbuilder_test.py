import sys
import json

def main():
    # 获取命令行参数
    task_id = sys.argv[1]
    mapfile_path = sys.argv[2]
    function_name = sys.argv[3]
    assist_input = sys.argv[4]
    param1 = sys.argv[5]
    param2 = sys.argv[6]
    param3 = sys.argv[7]
    param4 = sys.argv[8]
    user_id = sys.argv[9]
    model_scope_str = sys.argv[10]  # 模型作用范围

    # 解析 model_scope
    try:
        model_scope = json.loads(model_scope_str)
        if not model_scope:
            print("No model scope provided.")
        else:
            print("Model scope coordinates:", model_scope)
    except json.JSONDecodeError as e:
        print(f"Error decoding model scope: {e}")
        model_scope = []

    # 你的业务逻辑
    print(f"Task ID: {task_id}, Function: {function_name}, User ID: {user_id}")
    print(f"Params: {param1}, {param2}, {param3}, {param4}")
    print(f"Assist Input: {assist_input}")

if __name__ == "__main__":
    main()