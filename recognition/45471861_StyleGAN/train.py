# !/user/bin/env python
"""
The module controls the StyleGAN training
"""
import os.path

import tensorflow as tf
from time import time
from models import Generator, Discriminator
import matplotlib.pyplot as plt
import neptune.new as neptune
from datetime import datetime
from tensorflow.keras import layers
from tensorflow.keras.utils import image_dataset_from_directory

__author__ = "Zhien Zhang"
__email__ = "zhien.zhang@uqconnect.edu.au"


class RandomWeightedAverage(layers.Layer):
    """
    Provides a (random) weighted average between real and generated image samples
    """

    def __init__(self, batch_size):
        super().__init__()
        self.batch_size = batch_size

    def call(self, real, fake, **kwargs):
        alpha = tf.random.normal((self.batch_size, 1, 1, 1), 0, 1)
        diff = fake - real
        return real + alpha * diff


class Trainer:
    """
    Controls the training of the model
    """
    def __init__(self, data_folder: str, output_dir: str, g_input_res, g_init_filters, d_final_res, d_input_filters,
                 image_res=64, channels=1, latent_dim=100, batch=128, epochs=20, checkpoint=1, lr=0.0002,
                 beta_1=0.5, validation_images=16, seed=1, n_critics=2, gp_weight=10.0, use_neptune=False):

        self.image_res = image_res
        self.channels = channels
        self.rgb = (channels == 3)
        self.latent_dim = latent_dim
        self.batch = batch
        self.epochs = epochs
        self.checkpoint = checkpoint
        self.lr = lr
        self.beta_1 = beta_1
        self.n_critics = n_critics  # the ratio of D training iterations and G training iterations
        self.gp_weight = gp_weight
        self.num_of_validation_images = validation_images
        self.output_dir = self._create_output_folder(output_dir)

        # initialize models
        self.generator = Generator(lr, beta_1, latent_dim, g_input_res, image_res, g_init_filters)
        self.generator.build()
        self.discriminator = Discriminator(lr, beta_1, image_res, d_final_res, d_input_filters)
        self.discriminator.build()

        # data
        self.dataset = None
        if channels == 1:
            color_mod = "grayscale"
        else:
            color_mod = "rgb"
        self.load_data(data_folder, (image_res, image_res), color_mod=color_mod)

        # latent code for validation
        self.validation_latent = tf.random.normal([self.num_of_validation_images, latent_dim], seed=seed)

        # credential for neptune
        self.neptune = use_neptune
        self.run = None
        if self.neptune:
            with open("neptune_credential.txt", 'r') as credential:
                token = credential.readline()

            self.run = neptune.init(
                project="zhien.zhang/styleGAN",
                api_token=token,
            )

            # record hyper-parameters of this training
            self.run["Image resolution"] = image_res
            self.run["Epochs"] = epochs
            self.run["Batch size"] = self.batch
            self.run["Latent dim"] = self.latent_dim
            self.run["G input resolution"] = g_input_res
            self.run["G initial filters"] = g_init_filters
            self.run["D input filters"] = d_input_filters
            self.run["D final resolution"] = d_final_res
            self.run["n_critics"] = n_critics

    @staticmethod
    def _create_output_folder(upper_folder: str) -> str:
        run_folder = datetime.now().strftime("%d-%m/%Y_%H_%M_%S")
        output_folder = os.path.join(upper_folder, run_folder)
        os.makedirs(output_folder, exist_ok=True)
        return output_folder

    def load_data(self, image_folder, image_size: tuple, color_mod="grayscale"):
        train_batches = image_dataset_from_directory(
            image_folder, labels=None, label_mode=None,
            class_names=None, color_mode=color_mod, batch_size=self.batch, image_size=image_size, shuffle=True,
            seed=None,
            validation_split=None, subset=None,
            interpolation='bilinear', follow_links=False,
            crop_to_aspect_ratio=False
        )
        self.dataset = train_batches

    def _train_g(self, fade_in) -> tuple:
        latent = tf.random.normal([self.batch, self.latent_dim])

        with tf.GradientTape() as tape:
            fake = self.generator.model(latent, training=True)
            fake_score = self.discriminator.model(fake, fade_in, training=False)
            loss = self.generator.loss(fake_score)

        gradient = tape.gradient(loss, self.generator.model.trainable_variables)
        self.generator.optimizer.apply_gradients(zip(gradient, self.generator.model.trainable_variables))

        return loss

    def _train_d(self, real, fade_in) -> tuple:
        with tf.GradientTape() as tape:
            latent = tf.random.normal([self.batch, self.latent_dim])
            fake = self.generator.model(latent, training=False)

            real_score = self.discriminator.model(real, fade_in, training=True)
            fake_score = self.discriminator.model(fake, fade_in, training=True)
            d_cost = self.discriminator.loss(real_score, fake_score)

            # Construct weighted average between real and fake images
            interpolated_img = RandomWeightedAverage(self.batch)(real, fake)
            # get gradient penalty loss
            gp = self.discriminator.gradient_penalty_loss(interpolated_img, fade_in)

            d_loss = d_cost + gp * self.gp_weight

        gradient = tape.gradient(d_loss, self.discriminator.model.trainable_variables)
        self.discriminator.optimizer.apply_gradients(zip(gradient, self.discriminator.model.trainable_variables))

        return d_loss

    def _show_images(self, epoch, save=True) -> plt.Figure:
        predictions = self.generator.model(self.validation_latent, training=False)

        fig = plt.figure(figsize=(7, 7))

        predictions = tf.reshape(predictions, (-1, self.image_res, self.image_reso, self.channels))
        for i in range(predictions.shape[0]):
            plt.subplot(4, 4, i + 1)

            if self.rgb:
                plt.imshow(predictions[i, :, :, :] * 0.5 + 0.5)
            else:
                plt.imshow(predictions[i, :, :, :] * 127.5 + 127.5, cmap='gray')
            plt.axis('off')

        if save:
            path = os.path.join(self.output_dir, 'image_at_epoch_{}.png'.format(epoch))
            plt.savefig(path)

        plt.show()

        return fig

    def train(self):
        # clip value for model weights
        clip_value = 0.01

        iter = 0

        # training metrics for D
        d_training_loss_buff = []
        last_d_training_loss = 0
        last_g_training_loss = 0

        # epoch loop
        for epoch in range(self.epochs):
            start = time()
            # increase the fade in ratio as the number of epochs trained increases
            fade_in = epoch / float(self.epochs - 1)

            # train each batch inside of the dataset
            for image_batch in self.dataset:
                # normalize to the range [-1, 1] to match the generator output
                image_batch = (image_batch - 255 / 2) / (255 / 2)

                d_loss = self._train_d(image_batch, fade_in)
                d_training_loss_buff.append(d_loss)

                # train G for every self.n_critics of D training iterations
                if (iter + 1) % self.n_critics == 0:
                    g_loss = self._train_g(fade_in)

                    # calculate the D training metrics
                    d_training_loss_avg = sum(d_training_loss_buff) / len(d_training_loss_buff)

                    # log to neptune
                    if self.neptune:
                        self.run["G_loss"].log(g_loss)
                        self.run["D_loss"].log(d_training_loss_avg)

                    d_training_loss_buff = []
                    last_d_training_loss = d_training_loss_avg
                    last_g_training_loss = g_loss

                iter += 1

                # showing the result every 100 iterations
                if iter % 100 == 0:
                    fig = self._show_images(0, save=False)
                    if self.neptune:
                        self.run["Validation"].upload(fig)

            # show and save the result
            if epoch % self.checkpoint == 0:
                self._show_images(epoch, save=True)
                print('Time for epoch {} is {} sec'.format(epoch + 1, time() - start))
                print("D_loss: {}\t G_loss: {}".format(last_d_training_loss, last_g_training_loss))

        # save D and G
        folder = os.path.join(self.output_dir, "Model")
        g_folder = os.path.join(folder, "G")
        d_folder = os.path.join(folder, "D")
        self.generator.model.save(g_folder)
        self.discriminator.model.save(d_folder)
