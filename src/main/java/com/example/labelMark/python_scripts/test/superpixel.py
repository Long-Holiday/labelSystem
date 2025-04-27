import cv2
import numpy as np

def superpixel_segmentation_lsc(image_path, region_size=10, ratio=0.075):
    """
    使用 OpenCV 的 createSuperpixelLSC 函数对 TIFF 图像进行超像素分割。

    Args:
        image_path (str): TIFF 图像的路径。
        region_size (int):  平均超像素大小（以像素为单位）。
        ratio (float):  超像素紧凑性因子 (0-1)。 值越大，形状越规则。

    Returns:
        tuple: 包含以下内容的元组：
            - segments (numpy.ndarray):  一个与输入图像大小相同的整数数组，
                                       其中每个整数表示像素所属的超像素的标签。
            - num_labels (int): 实际生成的超像素数量。
            - mask_image (numpy.ndarray): 可视化超像素边界的图像（可选，用于展示）。
    """

    # 读取 TIFF 图像
    image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"无法读取图像：{image_path}")

    # 获取图像尺寸和通道数, 如果是灰度图，需要转成3维
    if len(image.shape) == 2:
        image = image[:,:,np.newaxis]

    # 数据类型转换 (如有必要)
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    # 可选：高斯模糊和平滑 (对于彩色图像效果更好)
    # image = cv2.GaussianBlur(image, (3, 3), 0)

    # 可选: 如果是多通道，可以转换为 CIE Lab 色彩空间
    # if image.shape[2] == 3: # 仅对 3 通道图像进行转换
    #    image = cv2.cvtColor(image, cv2.COLOR_BGR2Lab)


    # 创建 SuperpixelLSC 对象
    lsc = cv2.ximgproc.createSuperpixelLSC(image, region_size=region_size, ratio=ratio)

    # 执行分割, 可调整迭代次数
    lsc.iterate(num_iterations=10)

    # 获取分割结果
    segments = lsc.getLabels()
    num_labels = lsc.getNumberOfSuperpixels()

    # 可视化超像素边界 (可选)
    mask = lsc.getLabelContourMask()
    mask_image = cv2.cvtColor(image[:,:,:3].copy() if image.shape[2]>=3 else image.copy(), cv2.COLOR_GRAY2BGR) if image.shape[2] <3 else image[:,:,:3].copy() #转为BGR显示

    mask_image[mask == 255] = [0, 0, 255]  # 将边界设置为红色

    return segments, num_labels, mask_image


if __name__ == '__main__':
    # 示例用法
    image_path = '/home/change/PycharmProjects/test3.tif'  # 替换为你的 TIFF 图像路径
    try:
        # 使用 LSC 算法
        segments_lsc, num_superpixels_lsc, mask_image_lsc = superpixel_segmentation_lsc(image_path)
        print(f"LSC - 实际生成的超像素数量: {num_superpixels_lsc}")


        # 显示分割结果（可选）
        cv2.imshow("Superpixel Segmentation (LSC)", mask_image_lsc)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # 保存分割结果 (可选)
        # np.save('segments_lsc.npy', segments_lsc)
        # cv2.imwrite('superpixel_boundaries_lsc.png', mask_image_lsc)

    except ValueError as e:
        print(f"错误：{e}")
    except cv2.error as e:
        print(f"OpenCV 错误: {e}")
        print("请确保你已经正确安装了 opencv-contrib-python。")
        print("可以使用以下命令安装：")
        print("pip install opencv-contrib-python")