# models/deeplab.py
import torch
import torch.nn as nn
from torchvision import models

class DeepLabV3Plus(nn.Module):
    def __init__(self, in_channels, num_classes):
        super(DeepLabV3Plus, self).__init__()
        self.deeplab = models.segmentation.deeplabv3_resnet101(pretrained=False)
        
        # 修改第一层卷积以支持自定义输入通道数
        self.deeplab.backbone.conv1 = nn.Conv2d(
            in_channels=in_channels,
            out_channels=64,
            kernel_size=7,
            stride=2,
            padding=3,
            bias=False
        )
        
        # 修改分类器的输出层以匹配 num_classes
        self.deeplab.classifier[4] = nn.Conv2d(256, num_classes, kernel_size=1)

    def forward(self, x):
        return self.deeplab(x)['out']