from models import VQVAE
from helper import *
import torch
import torch.nn as nn
import torchvision
from torchvision import datasets, transforms
import numpy as np
import matplotlib.pyplot as plt

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# transform = transforms.Compose(
#     [transforms.Grayscale(num_output_channels=1),
#      transforms.ToTensor(),
#      ])

# train_data = datasets.MNIST(
#     root = './data',
#     train = True,                         
#     transform = transform, 
#     download = True,            
# )

# test_data = datasets.MNIST(
#     root = './data', 
#     train = False, 
#     transform = transform,
#     download = True,  
# )

train_data = preload_imgs('D:\学习\COMP3710\demo2\keras_png_slices_data\keras_png_slices_train')
valid_data = preload_imgs('D:\学习\COMP3710\demo2\keras_png_slices_data\keras_png_slices_validate')
test_data = preload_imgs('D:\学习\COMP3710\demo2\keras_png_slices_data\keras_png_slices_test')

EPOCH_SIZE = 50
BATCH_SIZE = 128
LR = 0.002
K = 512
D = 64

train_loader = torch.utils.data.DataLoader(train_data, batch_size=BATCH_SIZE, 
                                           shuffle=True, num_workers=0)

valid_loader = torch.utils.data.DataLoader(valid_data, batch_size=BATCH_SIZE,
                                           shuffle=True, num_workers=0)

test_loader = torch.utils.data.DataLoader(test_data, batch_size=BATCH_SIZE, 
                                          shuffle=True, num_workers=0)

vqvae = VQVAE(1, K, D).to(device)
optim = torch.optim.Adam(params=vqvae.parameters(), lr=LR)
train_status = train(vqvae, optim, EPOCH_SIZE, train_loader)


