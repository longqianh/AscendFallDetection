import sys
# sys.path.insert(0, '')
sys.path.append('..')

import torch
import torch.nn as nn
from model.activation import activation_factory


class TemporalConv(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, dilation=1):
        super(TemporalConv, self).__init__()

        pad = (kernel_size + (kernel_size - 1) * (dilation - 1) - 1) // 2

        # add
        # ------
        self.flag = 0
        if dilation > 1 and stride > 1:
            stride = 1
            self.flag = 1

        # ------

        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=(kernel_size, 1),
            padding=(pad, 0),
            stride=(stride, 1),
            dilation=(dilation, 1))

        self.bn = nn.BatchNorm2d(out_channels)

        # add ---
        if self.flag:
            self.pool = nn.MaxPool2d(kernel_size=(
                kernel_size, 1), stride=(2, 1), dilation=(1, 1), padding=(1, 0))

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)

        # add ---
        if self.flag:
            x = self.pool(x)
        return x


class MultiScale_TemporalConv(nn.Module):
    def __init__(self,
                 in_channels,
                 out_channels,
                 kernel_size=3,
                 stride=1,
                 dilations=[1, 2, 3, 4],
                 residual=True,
                 residual_kernel_size=1,
                 activation='relu'):

        super().__init__()
        assert out_channels % (
            len(dilations) + 2) == 0, '# out channels should be multiples of # branches'

        # Multiple branches of temporal convolution
        self.num_branches = len(dilations) + 2
        branch_channels = out_channels // self.num_branches

        # Temporal Convolution branches
        self.branches = nn.ModuleList([
            nn.Sequential(
                nn.Conv2d(
                    in_channels,
                    branch_channels,
                    kernel_size=1,
                    padding=0),
                nn.BatchNorm2d(branch_channels),  # 正则化层，解决梯度消失或梯度爆炸问题
                activation_factory(activation),
                TemporalConv(
                    branch_channels,
                    branch_channels,
                    kernel_size=kernel_size,
                    stride=stride,
                    dilation=dilation),
            )
            for dilation in dilations
        ])

        # Additional Max & 1x1 branch
        self.branches.append(nn.Sequential(
            nn.Conv2d(in_channels, branch_channels, kernel_size=1, padding=0),
            nn.BatchNorm2d(branch_channels),
            activation_factory(activation),
            nn.MaxPool2d(kernel_size=(3, 1), stride=(
                stride, 1), padding=(1, 0)),
            nn.BatchNorm2d(branch_channels)
        ))

        self.branches.append(nn.Sequential(
            nn.Conv2d(in_channels, branch_channels, kernel_size=1,
                      padding=(0, 0), stride=(stride, 1)),
            nn.BatchNorm2d(branch_channels)
        ))

        # Residual connection

        # 残差层，解决网络退化问题，让网络的冗余层产生恒等映射
        if not residual:
            self.residual = lambda x: 0
        elif (in_channels == out_channels) and (stride == 1):  # 维度匹配，shortcut为实线
            self.residual = lambda x: x
        else:
            self.residual = TemporalConv(
                in_channels, out_channels, kernel_size=residual_kernel_size, stride=stride)
            # 唯独不匹配 处理方式暂时不太理解

        self.act = activation_factory(activation)

    def forward(self, x):
        # Input dim: (N,C,T,V)
        # print('#')
        res = self.residual(x)
        branch_outs = []
        for tempconv in self.branches:
            out = tempconv(x)
            branch_outs.append(out)

        # for b in branch_outs:
        #     print(b.shape)
        out = torch.cat(branch_outs, dim=1)  # 横着拼起来
        out += res
        out = self.act(out)
        return out


if __name__ == "__main__":
    m = MultiScale_TemporalConv(288, 288)
    x = torch.randn(32, 288, 100, 20)
    # m(x)
    # import tensorflow as tf
    # mtf = tf.keras.models.load_model('./mstcn.pb')
    # mtf.summary()
    # mtf(x)
    # torch.onnx.export(m, x, 'mstcn.onnx', opset_version=12)
    # from onnx_tf.backend import prepare
    # import onnx
    # om = onnx.load('mstcn.onnx')
    # tf = prepare(om)
    # tf.export_graph('mstcn.pb')
    # mstcn.forward(x)
    # for name, param in mstcn.named_parameters():
    ''' named_parameters(): 
     Returns an iterator over module parameters,
     yielding both the name of the parameter 
     as well as the parameter itself. '''
    # print(f'{name}: {param.numel()}')
    # print(sum(p.numel() for p in mstcn.parameters() if p.requires_grad))
    ''' numel: 
    Returns the total number of elements in the input tensor.
    '''
    print(m(x).shape)
