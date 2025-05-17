import torch

print('CUDA 是否可用:', torch.cuda.is_available())
print('PyTorch 版本:', torch.__version__)
if torch.cuda.is_available():
    print('CUDA 版本:', torch.version.cuda)
    print('GPU 數量:', torch.cuda.device_count())
    print('GPU 名稱:', torch.cuda.get_device_name(0))
else:
    print('未找到可用的 GPU') 