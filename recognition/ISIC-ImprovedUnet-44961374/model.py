"""
This script creates an Improved U-Net model.
Specifications of the model can be found at: https://arxiv.org/abs/1802.10508v1
@author: Mujibul Islam Dipto
"""
import tensorflow as tf
from tensorflow.keras.layers import Conv2D, Activation, BatchNormalization, \
    Dropout, Input, concatenate, Add, UpSampling2D, Conv2DTranspose, LeakyReLU
from tensorflow_addons.layers import InstanceNormalization
from tensorflow.keras.layers import  Conv2D


# GLOBAL CONSTANTS (values taken from the paper)
P_DROP = 0.3 # dropout probability
NUM_STRIDES = 2 # number of input strides
LEAKY_RELU_ALPHA = 1e-2 # slope of LeakyReLU
IMAGE_ROWS = 256 # image x dimension
IMAGE_COLS = 256 # image y dimension
IMAGE_CHANNELS = 1 # greyscale
KERNEL_SIZE = (3,3) # size of kernel


def create_conv2d(input_layer, filters, kernel_size):
    """Creates a Conv2D layer based on the Improved UNet architecture. 
    Please look at the README.md for more details.

    Args:
        input_layer (keras.layer): input layer to this conv2d layer
        filters (int): number of filters
        kernel_size (tuple): size of the kernel

    Returns:
        keras.layer.Conv2D: the conv2d layer that has been created
    """
    conv2d_layer = Conv2D(filters=filters, kernel_size=kernel_size, padding='same', activation=LeakyReLU(alpha=LEAKY_RELU_ALPHA))(input_layer)
    return conv2d_layer


def context_module(input_layer, filters):
    """Creates a context module based on the Improved UNet architecture. Contains a pre-activation residual block with 
    two 3x3 conv layers and a dropout layer with probability = 0.3
    These modules are connected by 3x3 convs with input stride 2 to reduce the resolution of the feature maps.
    This allows for more features while descending down the aggregation pathway.
    Source: https://arxiv.org/pdf/1802.10508v1.pdf

    Args:
        input_layer (keras.layer): input layer to this module
        filters (int): number of filters

    Returns:
        [keras.layer]: final layer of this module
    """
    instance_norm_layer1 = InstanceNormalization()(input_layer)
    conv_layer1 = create_conv2d(instance_norm_layer1, filters, KERNEL_SIZE)
    dropout = Dropout(P_DROP)(conv_layer1)
    instance_norm_layer2 = InstanceNormalization()(dropout)
    conv_layer2 = create_conv2d(instance_norm_layer2, filters, KERNEL_SIZE)
    return conv_layer2

def upsampling_module(input_layer, filters):
    """Creates an upsampling module based on the Improved Unet architecture.
    Performs 2d upsampling, followed by 3x3 convolution.

    Args:
        input_layer (keras.layer): input layer to this module
        filters (int): number of filters

    Returns:
        keras.layer: final layer of this module
    """
    upsampling_layer = UpSampling2D(KERNEL_SIZE)(input_layer)
    conv2d = create_conv2d(upsampling_layer, filters, KERNEL_SIZE)
    return conv2d

def localization_module(input_layer, filters):
    """Creates a localization module based on the Improved UNet architecture.
    Contains two conv2d layers with a LeakyReLU activation function and slope = 0.01

    Args:
        input_layer (keras.layer): input layer to this module
        filters (int): number of filters

    Returns:
        keras.layer: final layer of this module
    """
    conv_layer1 = create_conv2d(input_layer, filters, KERNEL_SIZE)
    conv_layer2 = create_conv2d(conv_layer1, filters, (1,1))
    return conv_layer2

def create_model():
    ########## INPUT ##########
    input_layer = Input(shape=(IMAGE_ROWS, IMAGE_COLS, IMAGE_CHANNELS))

    ########## CONTRACTING PATH ##########
    conv_layer1 = create_conv2d(input_layer, 16, KERNEL_SIZE)
    context1 = context_module(conv_layer1, 16)

create_model()

