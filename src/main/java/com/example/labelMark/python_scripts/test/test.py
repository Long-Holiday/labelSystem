# test.py
import sys

def Test(task_id):
    print(task_id)  #直接打印接收到的task_id
    return task_id #如果需要返回值的话
    # ... 其他代码 ...

if __name__ == "__main__":
    if len(sys.argv) > 1:  # 检查是否有参数传入 (sys.argv[0] 是脚本名)
        task_id = int(sys.argv[1])  # 获取第一个参数（taskId），并转换为整数
        result = Test(task_id) #调用函数
        print(result)  #重要：将结果打印到标准输出，java才能读取到
    else:
        print("No task ID provided.") #如果没有收到参数