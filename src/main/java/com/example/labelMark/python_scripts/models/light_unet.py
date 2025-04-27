# models/light_unet.py
import torch
import torch.nn as nn

class LightUNet(nn.Module):
    def __init__(self, in_channels, num_classes):
        super(LightUNet, self).__init__()
        self.encoder_conv1 = nn.Conv2d(in_channels, 32, kernel_size=3, padding=1)
        self.encoder_conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        self.decoder_upconv1 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
        self.decoder_conv1 = nn.Conv2d(32 + 32, 32, kernel_size=3, padding=1)
        self.decoder_conv2 = nn.Conv2d(32, num_classes, kernel_size=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        enc1 = self.relu(self.encoder_conv1(x))
        enc2 = self.relu(self.encoder_conv2(self.pool(enc1)))
        dec1 = self.decoder_upconv1(enc2)
        dec1_upsampled = torch.nn.functional.interpolate(dec1, size=enc1.shape[-2:], mode='bilinear', align_corners=False)
        dec1_concat = torch.cat([dec1_upsampled, enc1], dim=1)
        dec2 = self.relu(self.decoder_conv1(dec1_concat))
        output = self.decoder_conv2(dec2)
        return output

# import torch
# import torch.nn as nn

# # 定义SE模块
# class SEBlock(nn.Module):
#     def __init__(self, in_channels, reduction=16):
#         super(SEBlock, self).__init__()
#         self.squeeze = nn.AdaptiveAvgPool2d(1)  # 全局平均池化
#         self.excitation = nn.Sequential(
#             nn.Linear(in_channels, in_channels // reduction, bias=False),
#             nn.ReLU(inplace=True),
#             nn.Linear(in_channels // reduction, in_channels, bias=False),
#             nn.Sigmoid()
#         )

#     def forward(self, x):
#         b, c, _, _ = x.size()
#         y = self.squeeze(x).view(b, c)  # 压缩为 [B, C]
#         y = self.excitation(y).view(b, c, 1, 1)  # 生成权重 [B, C, 1, 1]
#         return x * y.expand_as(x)  # 应用权重

# # 修改后的LightUNet
# class LightUNet(nn.Module):
#     def __init__(self, in_channels, num_classes):
#         super(LightUNet, self).__init__()
#         self.encoder_conv1 = nn.Conv2d(in_channels, 32, kernel_size=3, padding=1)
#         self.se1 = SEBlock(32)  # 在第一个卷积层后加入SE模块
#         self.encoder_conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
#         self.se2 = SEBlock(64)  # 在第二个卷积层后加入SE模块
#         self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
#         self.decoder_upconv1 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
#         self.decoder_conv1 = nn.Conv2d(32 + 32, 32, kernel_size=3, padding=1)
#         self.decoder_conv2 = nn.Conv2d(32, num_classes, kernel_size=1)
#         self.relu = nn.ReLU()

#     def forward(self, x):
#         # 编码器
#         enc1 = self.relu(self.encoder_conv1(x))
#         enc1 = self.se1(enc1)  # 应用SE模块
#         enc2 = self.relu(self.encoder_conv2(self.pool(enc1)))
#         enc2 = self.se2(enc2)  # 应用SE模块
#         # 解码器
#         dec1 = self.decoder_upconv1(enc2)
#         dec1_upsampled = torch.nn.functional.interpolate(dec1, size=enc1.shape[-2:], mode='bilinear', align_corners=False)
#         dec1_concat = torch.cat([dec1_upsampled, enc1], dim=1)
#         dec2 = self.relu(self.decoder_conv1(dec1_concat))
#         output = self.decoder_conv2(dec2)
#         return output

# # 定义Dice Loss
# class DiceLoss(nn.Module):
#     def __init__(self, smooth=1e-6):
#         super(DiceLoss, self).__init__()
#         self.smooth = smooth

#     def forward(self, preds, targets):
#         # preds: [B, C, H, W], targets: [B, H, W]
#         if preds.shape[1] == 1:  # 二分类
#             preds = torch.sigmoid(preds)
#             preds = preds.view(-1)
#             targets = targets.view(-1)
#             intersection = (preds * targets).sum()
#             dice = (2. * intersection + self.smooth) / (preds.sum() + targets.sum() + self.smooth)
#         else:  # 多分类
#             preds = torch.softmax(preds, dim=1)
#             targets_one_hot = torch.nn.functional.one_hot(targets, num_classes=preds.shape[1]).permute(0, 3, 1, 2).float()
#             intersection = (preds * targets_one_hot).sum(dim=(2, 3))
#             sum_preds = preds.sum(dim=(2, 3))
#             sum_targets = targets_one_hot.sum(dim=(2, 3))
#             dice = (2. * intersection + self.smooth) / (sum_preds + sum_targets + self.smooth)
#             dice = dice.mean(dim=1).mean()  # 平均类别和批次
#         return 1 - dice

# import torch
# import torch.nn as nn
# import torch.nn.functional as F

# # 定义轻量级通道注意力模块 (SE Block)
# class SEBlock(nn.Module):
#     def __init__(self, in_channels, reduction=16):
#         super(SEBlock, self).__init__()
#         self.squeeze = nn.AdaptiveAvgPool2d(1)  # 全局平均池化
#         self.excitation = nn.Sequential(
#             nn.Linear(in_channels, in_channels // reduction, bias=False),
#             nn.ReLU(inplace=True),
#             nn.Linear(in_channels // reduction, in_channels, bias=False),
#             nn.Sigmoid()
#         )

#     def forward(self, x):
#         b, c, _, _ = x.size()
#         y = self.squeeze(x).view(b, c)  # 压缩为 [B, C]
#         y = self.excitation(y).view(b, c, 1, 1)  # 生成通道权重
#         return x * y.expand_as(x)  # 应用权重

# # 定义残差卷积块
# class ResidualBlock(nn.Module):
#     def __init__(self, in_channels, out_channels):
#         super(ResidualBlock, self).__init__()
#         self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
#         self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1)
#         self.relu = nn.ReLU(inplace=True)
#         self.se = SEBlock(out_channels)  # 引入注意力机制

#         # 如果输入输出通道数不同，使用1x1卷积调整维度
#         if in_channels != out_channels:
#             self.shortcut = nn.Conv2d(in_channels, out_channels, kernel_size=1)
#         else:
#             self.shortcut = nn.Identity()

#     def forward(self, x):
#         identity = self.shortcut(x)  # 残差连接的捷径分支
#         out = self.relu(self.conv1(x))
#         out = self.conv2(out)
#         out = self.se(out)  # 应用注意力机制
#         out += identity  # 残差连接
#         out = self.relu(out)
#         return out

# # 修改后的 LightUNet
# class LightUNet(nn.Module):
#     def __init__(self, in_channels, num_classes):
#         super(LightUNet, self).__init__()
#         # 编码器
#         self.enc1 = ResidualBlock(in_channels, 32)
#         self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)
#         self.enc2 = ResidualBlock(32, 64)
#         self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)
#         self.enc3 = ResidualBlock(64, 128)  # 增加一层编码器

#         # 解码器
#         self.upconv2 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
#         self.dec2 = ResidualBlock(64 + 64, 64)  # 64 (上采样) + 64 (跳跃连接)
#         self.upconv1 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)
#         self.dec1 = ResidualBlock(32 + 32, 32)  # 32 (上采样) + 32 (跳跃连接)

#         # 输出层
#         self.final_conv = nn.Conv2d(32, num_classes, kernel_size=1)
#         self.relu = nn.ReLU(inplace=True)

#     def forward(self, x):
#         # 编码器
#         enc1 = self.enc1(x)
#         pool1 = self.pool1(enc1)
#         enc2 = self.enc2(pool1)
#         pool2 = self.pool2(enc2)
#         enc3 = self.enc3(pool2)

#         # 解码器
#         up2 = self.upconv2(enc3)
#         up2 = F.interpolate(up2, size=enc2.shape[-2:], mode='bilinear', align_corners=False)  # 双线性插值优化
#         dec2_concat = torch.cat([up2, enc2], dim=1)  # 跳跃连接
#         dec2 = self.dec2(dec2_concat)

#         up1 = self.upconv1(dec2)
#         up1 = F.interpolate(up1, size=enc1.shape[-2:], mode='bilinear', align_corners=False)  # 双线性插值优化
#         dec1_concat = torch.cat([up1, enc1], dim=1)  # 跳跃连接
#         dec1 = self.dec1(dec1_concat)

#         # 输出
#         output = self.final_conv(dec1)
#         return output

# # 测试代码
# if __name__ == "__main__":
#     model = LightUNet(in_channels=3, num_classes=2)
#     x = torch.randn(1, 3, 256, 256)
#     output = model(x)
#     print(f"Input shape: {x.shape}")
#     print(f"Output shape: {output.shape}")