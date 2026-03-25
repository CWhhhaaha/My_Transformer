import torch
import numpy as np

print("Torch version:", torch.__version__)
print("Numpy version:", np.__version__)

# 测试 tensor 运算
x = torch.randn(2, 3)
y = torch.randn(2, 3)

z = x + y

print("Tensor test OK:", z.shape)

# 测试简单矩阵乘法（attention核心）
q = torch.randn(2, 4)
k = torch.randn(2, 4)

score = torch.matmul(q, k.T)

print("Matmul OK:", score.shape)

print("Environment is READY 🚀")