import torch
import torch.nn as nn
import torch.nn.functional as F

from inference.models.grasp_model import GraspModel, ResidualBlock
from inference.cbam import CBAM


class AGRNet(GraspModel):

    def __init__(self, input_channels=4, output_channels=1, channel_size=32, dropout=False, prob=0.0):
        super(AGRNet, self).__init__()
        self.attn_weight = 0.05

        self.conv1 = nn.Conv2d(input_channels, channel_size, kernel_size=9, stride=1, padding=4)
        self.bn1 = nn.BatchNorm2d(channel_size)

        self.conv2 = nn.Conv2d(channel_size, channel_size * 2, kernel_size=4, stride=2, padding=1)
        self.bn2 = nn.BatchNorm2d(channel_size * 2)

        self.conv3 = nn.Conv2d(channel_size * 2, channel_size * 4, kernel_size=4, stride=2, padding=1)
        self.bn3 = nn.BatchNorm2d(channel_size * 4)

        self.res1 = ResidualBlock(channel_size * 4, channel_size * 4)
        self.res2 = ResidualBlock(channel_size * 4, channel_size * 4)
        self.res3 = ResidualBlock(channel_size * 4, channel_size * 4)
        self.res4 = ResidualBlock(channel_size * 4, channel_size * 4)
        self.res5 = ResidualBlock(channel_size * 4, channel_size * 4)

        self.fuse_conv = nn.Conv2d(8 * channel_size, 4 * channel_size, kernel_size=1, bias=False)
        self.fuse_bn = nn.BatchNorm2d(4 * channel_size)
        self.cbam3 = CBAM(channel_size * 4)
        self.cbam5 = CBAM(channel_size * 4)

        self.conv4 = nn.ConvTranspose2d(channel_size * 4, channel_size * 2, kernel_size=4, stride=2, padding=1,
                                        output_padding=1)
        self.bn4 = nn.BatchNorm2d(channel_size * 2)

        self.conv5 = nn.ConvTranspose2d(channel_size * 2, channel_size, kernel_size=4, stride=2, padding=2,
                                        output_padding=1)
        self.bn5 = nn.BatchNorm2d(channel_size)

        self.conv6 = nn.ConvTranspose2d(channel_size, channel_size, kernel_size=9, stride=1, padding=4)

        self.pos_output = nn.Conv2d(in_channels=channel_size, out_channels=output_channels, kernel_size=2)
        self.cos_output = nn.Conv2d(in_channels=channel_size, out_channels=output_channels, kernel_size=2)
        self.sin_output = nn.Conv2d(in_channels=channel_size, out_channels=output_channels, kernel_size=2)
        self.width_output = nn.Conv2d(in_channels=channel_size, out_channels=output_channels, kernel_size=2)

        self.dropout = dropout
        self.dropout_pos = nn.Dropout(p=prob)
        self.dropout_cos = nn.Dropout(p=prob)
        self.dropout_sin = nn.Dropout(p=prob)
        self.dropout_wid = nn.Dropout(p=prob)

        for m in self.modules():
            if isinstance(m, (nn.Conv2d, nn.ConvTranspose2d)):
                nn.init.xavier_uniform_(m.weight, gain=1)

    def forward(self, x_in):
        x1 = F.relu(self.bn1(self.conv1(x_in)))  # [B, C, H, W]
        x2 = F.relu(self.bn2(self.conv2(x1)))  # [B, 2C, H/2, W/2]
        x3 = F.relu(self.bn3(self.conv3(x2)))  # [B, 4C, H/4, W/4]

        x = self.res1(x3)
        x = self.res2(x)
        x = self.res3(x)
        x = self.res4(x)
        x5 = self.res5(x)  # [B, 4C, H/4, W/4]

        x3_attn = x3 * (1 + self.cbam3(x3) * self.attn_weight)
        x5_attn = x5 * (1 + self.cbam5(x5) * self.attn_weight)

        fused = torch.cat([x3_attn, x5_attn], dim=1)  # [B, 8C, H/4, W/4]
        x = F.relu(self.fuse_bn(self.fuse_conv(fused)))

        # Encoder
        x = F.relu(self.bn4(self.conv4(x)))
        x = F.relu(self.bn5(self.conv5(x)))
        x = self.conv6(x)

        if self.dropout:
            pos_output = self.pos_output(self.dropout_pos(x))
            cos_output = self.cos_output(self.dropout_cos(x))
            sin_output = self.sin_output(self.dropout_sin(x))
            width_output = self.width_output(self.dropout_wid(x))
        else:
            pos_output = self.pos_output(x)
            cos_output = self.cos_output(x)
            sin_output = self.sin_output(x)
            width_output = self.width_output(x)

        return pos_output, cos_output, sin_output, width_output
