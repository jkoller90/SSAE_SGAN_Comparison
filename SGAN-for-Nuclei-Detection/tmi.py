# -*- coding: utf-8 -*-
from __future__ import print_function, division

from keras.layers import Input, Dense, Reshape, Flatten, Dropout
from keras.layers import BatchNormalization, Activation, ZeroPadding2D
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.convolutional import UpSampling2D, Conv2D
from keras.models import Sequential, Model
from keras.optimizers import Adam
from keras.utils import to_categorical
from keras.utils.vis_utils import plot_model
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, average_precision_score
from skimage.transform import resize
import scipy.io

import click
import cv2
import matplotlib.pyplot as plt
import itertools
import numpy as np
import time
import shutil
import os
import mmappickle

# Fixing random state for reproducibility
seed = 19680801
np.random.seed(seed)

class SGAN():
    def __init__(self):
        # TMI input shape (after resized)is 32x32x3
        self.img_rows = 32
        self.img_cols = 32
        self.channels = 3
        self.num_classes = 2
        self.training_history = {
                'D_loss': [],
                'D_acc': [],
                'G_loss': [],
                'G_acc': [],
                }

        # While previous GAN work has used momentum to accelerate training, we used the Adam optimizer
        # (Kingma & Ba, 2014) with tuned hyperparameters. We found the suggested learning rate of 0.001,
        # to be too high, using 0.0002 instead. Additionally, we found leaving the momentum term β1 at the
        # suggested value of 0.9 resulted in training oscillation and instability while reducing it to 0.5 helped
        # stabilize training
        optimizer = Adam(0.0002, 0.5)

        # Build discriminator's model
        self.discriminator = self.build_discriminator()
        # Compile discriminator's model, i.e. define its learning process
        # binary crossentropy is used to distinguish among real or fake samples
        # categorical entropy is to distinguish among which real category is (nuclei or non-nuclei)
        self.discriminator.compile(
                loss=['binary_crossentropy', 'categorical_crossentropy'],
                loss_weights=[0.5, 0.5],
                optimizer=optimizer,
                metrics=['accuracy'])

        # Build the generator
        self.generator = self.build_generator()

        # The generator takes noise as input and generates imgs
        z = Input(shape=(100,))
        img = self.generator(z)

        # For the combined model we will only train the generator
        self.discriminator.trainable = False

        # The discriminator takes generated images as input and determines validity
        valid, _ = self.discriminator(img)

        # The combined model  (stacked generator and discriminator) takes
        # noise as input => generates images => determines validity
        self.combined = Model(z, valid)
        self.combined.compile(
                loss=['binary_crossentropy'], 
                optimizer=optimizer)

    def build_generator(self):
        # This model replaced any pooling layers with strided convolutions
        # Allowing it to learn its own spatial upsampling

        model = Sequential()

        model.add(Dense(128 * 8 * 8, activation='relu', input_dim=100))
        
        model.add(Reshape((8, 8, 128)))
        model.add(BatchNormalization(momentum=0.8))

        # fractionally-strided convolution, do not confuse with deconvolution operation
        model.add(UpSampling2D())
        model.add(Conv2D(128, kernel_size=3, padding='same'))
        # using a bounded activation allowed the model to learn more quickly to saturate
        # and cover the color space of the training distribution
        model.add(Activation('relu'))
        model.add(BatchNormalization(momentum=0.8))

        #upsampling is the opposite to pooling. Repeats the rows and columns of the data
        model.add(UpSampling2D())
        model.add(Conv2D(64, kernel_size=3, padding='same'))
        model.add(Activation('relu'))
        model.add(BatchNormalization(momentum=0.8))

        #flatten to the amount of channels
        model.add(Conv2D(self.channels, kernel_size=3, padding='same'))
        model.add(Activation('tanh'))
        
#        plot_path = 'generator.png'
#        plot_model(model, to_file=plot_path, show_shapes=True, show_layer_names=True)

        #model.summary()

        noise = Input(shape=(100,))
        img = model(noise)

        return Model(noise, img)

    def build_discriminator(self):
        # This model replaced any pooling layers with strided convolutions
        # Allowing it to learn its own spatial downsampling
        img_shape = (self.img_rows, self.img_cols, self.channels)

        # A Sequential model is a linear stack of layers.
        model = Sequential()

        # Create a Sequential model by simply adding layers via the .add() method
        # 32 filters, 3x3 kernel size, stride 2, input_shape is 28x28x1, same: pad so the output and input size are equal
        model.add(Conv2D(32, kernel_size=3, strides=2, input_shape=img_shape, padding='same'))
        # f(x) = alpha * x for x < 0, f(x) = x for x >= 0.
        # Leaky rectified activation worked well, especially for higher resolution modeling.
        # This is in contrast to the original GAN paper, which used the maxout activation
        model.add(LeakyReLU(alpha=0.2))
        # drops 25% of the input units
        model.add(Dropout(0.25))

        model.add(Conv2D(64, kernel_size=3, strides=2, padding='same'))
        #A zero-padding layer. Adds rows and columns of zeros to the image
        model.add(ZeroPadding2D(padding=((0,1),(0,1))))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        # Normalize the activations of the previous layer at each batch to reduce its covariance shift,
        # i.e., the amount that the distribution of each layer shift around.

        # This helps deal with training problems that arise due to poor initialization and helps gradient flow in deeper models.
        # This proved critical to get deep generators to begin learning, preventing the generator from collapsing all samples
        # to a single point which is a common failure mode observed in GANs.
        #
        # Directly applying batchnorm to all layers, however, resulted in sample oscillation and model instability.
        # This was avoided by not applying batchnorm to the generator output layer and the discriminator input layer
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(128, kernel_size=3, strides=2, padding='same'))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(256, kernel_size=3, strides=1, padding='same'))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))

        model.add(Flatten())
        #model.summary()
#        plot_path = 'discriminator.png'
#        plot_model(model, to_file=plot_path, show_shapes=True, show_layer_names=True)


        # instantiate a Keras tensor
        img = Input(shape=img_shape)
        features = model(img)

        # valid indicates if the image is real or fake
        valid = Dense(1, activation='sigmoid')(features)
        # iff the image is real, label indicates which type of image it is
        label = Dense(self.num_classes+1, activation='softmax')(features)

        # Given an img (x)  and a label(y), instantiate a Model.
        # Once instantiated, this model will include all layers required in the computation of y given x.
        return Model(img, [valid, label])

    def train(self, X_train, y_train, X_test, y_test, epochs, batch_size, save_interval):

        # delete directory if exist and create it
        shutil.rmtree('TMI_generators_output', ignore_errors=True)
        os.makedirs('TMI_generators_output')

        half_batch = int(batch_size / 2)

        # Class weights:
        # To balance the difference in occurences of class labels.
        # 50% of labels that D trains on are 'fake'.
        # Weight = 1 / frequency
        cw1 = {0: 1, 1: 1}
        cw2 = {i: self.num_classes / half_batch for i in range(self.num_classes)}
        cw2[self.num_classes] = 1 / half_batch

        for epoch in range(epochs):
            # ---------------------
            #  Training the Discriminator
            # ---------------------

            # Select a random half batch of images
            idx = np.random.randint(0, X_train.shape[0], half_batch)
            imgs = X_train[idx]

            # Draw random samples from a Gaussian distribution.
            noise = np.random.normal(0, 1, (half_batch, 100))
            # Generate a half batch of new images
            gen_imgs = self.generator.predict(noise)

            valid = np.ones((half_batch, 1))
            fake = np.zeros((half_batch, 1))

            # Convert labels to categorical one-hot encoding
            labels = to_categorical(y_train[idx], num_classes=self.num_classes+1)
            fake_labels = to_categorical(np.full((half_batch, 1), self.num_classes), num_classes=self.num_classes+1)

            # Train the discriminator (real classified as ones and fakes as zeros)
            # train_on_batch: Single gradient update over one batch of samples
            d_loss_real = self.discriminator.train_on_batch(imgs, [valid, labels], class_weight=[cw1, cw2])
            d_loss_fake = self.discriminator.train_on_batch(gen_imgs, [fake, fake_labels], class_weight=[cw1, cw2])
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)

            # ---------------------
            #  Training the Generator
            # ---------------------
            validity = np.ones((batch_size, 1))
            
            for i in range(10):
                noise = np.random.normal(0, 1, (batch_size, 100))
                # Train the generator (wants discriminator to mistake images as real)
                g_loss = self.combined.train_on_batch(noise, validity, class_weight=[cw1, cw2])

            self.training_history['D_loss'].append(d_loss[0]);
            self.training_history['D_acc'].append(100*d_loss[3]);
            self.training_history['G_loss'].append(g_loss);
            self.training_history['G_acc'].append(100*d_loss[4]);

            print ('%d: Training D [loss: %.4f, acc: %.2f%% ] - G [loss: %.4f, acc: %.2f%%]' % (epoch, d_loss[0], 100*d_loss[3], g_loss, 100*d_loss[4]))
            self.evaluate_discriminator(X_test, y_test)

            # If at save interval => save generated image samples
            if epoch % save_interval == 0:
                self.save_imgs(epoch)
                
    def evaluate_discriminator(self, X_test, y_test):
        valid = np.ones((y_test.shape[0], 1))

        # Convert labels to categorical one-hot encoding
        labels = to_categorical(y_test, num_classes=self.num_classes+1)

        #  Evaluating the trained Discriminator
        scores = self.discriminator.evaluate(X_test, [valid, labels], verbose=0)

        print('Evaluating D [loss:  %.4f, bi-loss: %.4f, cat-loss: %.4f, bi-acc: %.2f%%, cat-acc: %.2f%%]\n' %
              (scores[0], scores[1], scores[2], scores[3]*100, scores[4]*100))
#        print('\nEvaluating D [loss:  %.4f, acc: %.2f%%]' % (scores[0], scores[3]*100))

        return (scores[0], scores[3]*100)

    def save_imgs(self, epoch):
        r, c = 5, 5
        noise = np.random.normal(0, 1, (r * c, 100))
        gen_imgs = self.generator.predict(noise)

        # Rescale images from [-1..1] to [0..1] just to display purposes.
        gen_imgs = 0.5 * gen_imgs + 0.5

        fig, axs = plt.subplots(r, c)
        cnt = 0
        for i in range(r):
            for j in range(c):
                axs[i,j].imshow(gen_imgs[cnt, :,:])
                axs[i,j].axis('off')
                cnt += 1
        fig.savefig('./TMI_generators_output/tmi_%d.png' % epoch)
        plt.close()

    def save_model(self):

        def save(model, model_name):
            model_path = './TMI_saved_models/%s.json' % model_name
            weights_path = './TMI_saved_models/%s_weights.hdf5' % model_name
            options = {'file_arch': model_path,
                        'file_weight': weights_path}
            json_string = model.to_json()
            open(options['file_arch'], 'w').write(json_string)
            model.save_weights(options['file_weight'])

        shutil.rmtree('TMI_saved_models', ignore_errors=True)
        os.makedirs('TMI_saved_models')

        save(self.generator, 'TMI_gan_generator')
        save(self.discriminator, 'TMI_gan_discriminator')
        save(self.combined, 'TMI_gan_adversarial')

    def plot_training_history(self):
        fig, axs = plt.subplots(1,2,figsize=(15,5))
        plt.title('Training History')
        # summarize history for G and D accuracy
        axs[0].plot(range(1,len(self.training_history['D_acc'])+1),self.training_history['D_acc'])
        axs[0].plot(range(1,len(self.training_history['G_acc'])+1),self.training_history['G_acc'])
        axs[0].set_title('D and G Accuracy')
        axs[0].set_ylabel('Accuracy')
        axs[0].set_xlabel('Epoch')
        axs[0].set_xticks(np.arange(1,len(self.training_history['D_acc'])+1),len(self.training_history['D_acc'])/10)
        axs[0].set_yticks([n for n in range(0, 101,10)])
        axs[0].legend(['Discriminator', 'Generator'], loc='best')

        # summarize history for G and D loss
        axs[1].plot(range(1,len(self.training_history['D_loss'])+1),self.training_history['D_loss'])
        axs[1].plot(range(1,len(self.training_history['G_loss'])+1),self.training_history['G_loss'])
        axs[1].set_title('D and G Loss')
        axs[1].set_ylabel('Loss')
        axs[1].set_xlabel('Epoch')
        axs[1].set_xticks(np.arange(1,len(self.training_history['G_loss'])+1),len(self.training_history['G_loss'])/10)
        axs[1].legend(['Discriminator', 'Generator'], loc='best')
        plt.show()

    def predict(self, X_test, y_test):

        # Generating a predictions from the discriminator over the testing dataset
        y_pred = self.discriminator.predict(X_test)
        print(y_pred[1][:,:-1])
        # Formating predictions to remove the one_hot_encoding format
        y_pred = np.argmax(y_pred[1][:,:-1], axis=1)

        print ('\nOverall accuracy: %f%% \n' % (accuracy_score(y_test, y_pred) * 100))
        print ('\nAveP: %f%% \n' % (average_precision_score(y_test, y_pred) * 100))
        
        # Calculating and ploting a Classification Report
        class_names = ['Non-nunclei', 'Nuclei']
        print('Classification report:\n %s\n'
              % (classification_report(y_test, y_pred, target_names=class_names)))

        # Calculating and ploting Confusion Matrix
        cm = confusion_matrix(y_test, y_pred)
#        print('Confusion matrix:\n%s' % cm)

        plt.figure()
        plot_confusion_matrix(cm, class_names, title='Confusion matrix, without normalization')

        plt.figure()
        plot_confusion_matrix(cm, class_names, normalize=True, title='Normalized confusion matrix')

    def predict_proba(self, X_test):
        return self.discriminator.predict(X_test)



    def predict_nms(self, images):
        pass

    def load_weights(self):
        # load weights into new model
        self.generator.load_weights('./TMI_saved_models/TMI_gan_generator_weights.hdf5')
        self.discriminator.load_weights('./TMI_saved_models/TMI_gan_discriminator_weights.hdf5')
        # self.combined.load_weights('./TMI_saved_models/TMI_gan_adversarial_weights.hdf5')
        print('Weights loaded from disk')

def is_nuclei(cell):
    if len(np.transpose(np.nonzero(cell))) == 0:
        return False
    p_n = np.array(np.transpose(np.nonzero(cell))[0][:2])
    p_c = np.array([17, 17])
    dist = np.linalg.norm(p_n - p_c)
# #   if dist < 15 nuclei_arr.append(dist, p_n, or p_c?)
    return dist < 17

def plot_confusion_matrix(cm, classes,
                          normalize=False,
                          title='Confusion matrix',
                          cmap=plt.cm.Blues):
    '''
    This function prints and plots the confusion matrix.
    Normalization can be applied by setting `normalize=True`.
    '''
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt),
                 horizontalalignment='center',
                 color='white' if cm[i, j] > thresh else 'black')

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')

def load_TMI_data():
    # Load the dataset
    dataset = scipy.io.loadmat('TMI2015/training/training.mat')

    # cv2.imshow('train_x', dataset['train_x'][0])
    cv2.waitKey(0)
    # Split into train and test. Values are in range [0..1] as float64
    X_train = np.transpose(dataset['train_x'], (3, 0, 1, 2))
    print(X_train.shape)
    y_train = list(dataset['train_y'][0])
    
    X_test = np.transpose(dataset['test_x'], (3, 0, 1, 2))
    y_test = list(dataset['test_y'][0])
    
    # Change shape and range. 
    y_train = np.asarray(y_train).reshape(-1, 1)
    y_test = np.asarray(y_test).reshape(-1, 1)

#   1-> 0 : Non-nucleus. 2 -> 1: Nucleus
    y_test -= 1
    y_train -= 1

    # Resize to 32x32
    X_train_resized = np.empty([X_train.shape[0], 32, 32, X_train.shape[3]])
    for i in range(X_train.shape[0]):
        X_train_resized[i] = resize(X_train[i], (32, 32, 3), mode='reflect')

    X_test_resized = np.empty([X_test.shape[0], 32, 32, X_test.shape[3]])
    for i in range(X_test.shape[0]):
        X_test_resized[i] = resize(X_test[i], (32, 32, 3), mode='reflect')
    
    # Normalize images from [0..1] to [-1..1]
    X_train_resized = 2 * X_train_resized - 1
    X_test_resized = 2 * X_test_resized - 1
    return X_train_resized, y_train, X_test_resized, y_test

def train_model():
    X_train, y_train, X_test, y_test = load_TMI_data()

#    Instanciate a compiled model
    sgan = SGAN()

#    sgan.load_weights()

    start = time.time()
    
    epochs=200
    # Fit/Train the model
    sgan.train(X_train, y_train, X_test, y_test, epochs, batch_size=32, save_interval=5)

    end = time.time()
    print ('\nTraining time: %0.1f minutes \n' % ((end-start) / 60))

    #saved the trained model
    sgan.save_model()

#    plot training graph
    sgan.plot_training_history()


def image_for_prefix(prf):
    base_path = prf + '.tif'
    block_path = prf + '_block.tif'
    cell_path = prf + '_cell.tif'
    base_img = cv2.imread(base_path)
    block_img = cv2.imread(block_path, cv2.IMREAD_GRAYSCALE)
    cell_img = cv2.imread(cell_path)
    # x, y 

    block = cv2.findNonZero(block_img).squeeze()

    x,y = block[0] + 3
    x_0,y_0 = block[-1] - 2

    crop = base_img[y:y_0, x:x_0]
    cell = cell_img[y:y_0, x:x_0]
    return crop, cell

def sliding_windows(img_size, window_size, step):
    max_x, max_y = img_size
    w, h = window_size
    x,y = 0,0
    windows = []
    for x_0 in range(x, max_x - w, step):
        for y_0 in range(y, max_y - h, step):
            windows.append((y_0,x_0,y_0+h,x_0+w))

    return np.array(windows)

def nms(windows, proba, thresh, overlap_rate):
    pick = []
    boxes = windows
    # grab the coordinates of the bounding boxes
    x1 = boxes[:,0]
    y1 = boxes[:,1]
    x2 = boxes[:,2]
    y2 = boxes[:,3]

    # compute the area of the bounding boxes and sort the bounding
    # boxes by the bottom-right y-coordinate of the bounding box
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    # proba = proba[np.where(proba < thresh)]
    idxs = np.argsort(proba)
    t = proba[idxs]
    idxs = np.delete(idxs, np.where(t < thresh)[0])
    # keep looping while some indexes still remain in the indexes
    # list
    while len(idxs) > 0:
        # grab the last index in the indexes list and add the
        # index value to the list of picked indexes
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)
 
        # find the largest (x, y) coordinates for the start of
        # the bounding box and the smallest (x, y) coordinates
        # for the end of the bounding box
        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])
 
        # compute the width and height of the bounding box
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
 
        # compute the ratio of overlap
        overlap = (w * h) / area[idxs[:last]]
 
        # delete all indexes from the index list that have
        idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlap_rate)[0])))
 
    return pick


def prepare_patches(patches):
    X_test = np.asarray(patches)
    X_test_resized = np.empty([X_test.shape[0], 32, 32, X_test.shape[3]])
    for i in range(X_test.shape[0]):
        X_test_resized[i] = resize(X_test[i], (32, 32, 3), mode='reflect')
    
    # Normalize images from [0..1] to [-1..1]
    X_test_resized = 2 * X_test_resized - 1
    return X_test_resized

@click.group()
def cli():
   pass

@cli.command()
def test_predict():
    # X_test, y_test = load_TMI_test_data()
    X_train, y_train, X_test, y_test = load_TMI_data()

    print ("Loaded test data")
    sgan = SGAN()

    sgan.load_weights()

    sgan.evaluate_discriminator(X_test, y_test)

    sgan.predict(X_test, y_test)

@cli.command()
@click.option('-p', '--path', 
    type=click.Path(exists=True),
    help='Tests the current model against a provided dataset')
def test_model(path):
    print(path)
    sgan = SGAN()
    sgan.load_weights()

    m = mmappickle.mmapdict(path, readonly=True)
    all_preds = None
    all_tests = None
    print(m.keys())
    for key in list(m.keys())[:10]:
        print(key)
        d = m[key]
        crop = d['crop']
        cell = d['cell']
        print(d.keys())

        windows = sliding_windows((400, 400), (34, 34), 6)[:1]
        patches = [crop[w[0]:w[2], w[1]:w[3]] for w in windows]
        cell_patches = [cell[w[0]:w[2], w[1]:w[3]] for w in windows]
        y_test = np.array([is_nuclei(n) for n in cell_patches])
        try:
            y_proba = sgan.predict_proba(prepare_patches(patches))
            print(y_proba)
            y_proba = y_proba[1][:,:-1]
            print(y_proba)
            y_pred = np.argmax(y_proba, axis=1)
            print(y_pred)
        except Exception as e:
            print("Erro")
            continue
        else:
            pass
        return
    #     print(np.argwhere(y_pred == 1))
    #     return
        nuclei_picks = nms(windows, y_proba[:,1], 0.1, 0.3)
        print(nuclei_picks)
    #     print("Nuclei picks")
        non_nuclei_picks  = nms(windows, y_proba[:,0], 0.1, 0.3)
    #     print(nuclei_picks)
    #     print("Non nuclei picks")
    #     print(non_nuclei_picks)
        picks =  np.concatenate((nuclei_picks, non_nuclei_picks))
        print(picks)
    #     print(picks)
        y_test = y_test[picks]
        y_pred = y_pred[picks]

        if all_preds is None:
            all_preds = y_pred
            all_tests = y_test
        else:
            all_preds = np.concatenate((all_preds, y_pred))
            all_tests = np.concatenate((all_tests, y_test))

    print ('\nOverall accuracy: %f%% \n' % (accuracy_score(all_preds, all_tests) * 100))
    print ('\nAveP: %f%% \n' % (average_precision_score(all_preds, all_tests) * 100))
    
    # Calculating and ploting a Classification Report
    class_names = ['Non-nunclei', 'Nuclei']
    print('Classification report:\n %s\n'
          % (classification_report(all_preds, all_tests, target_names=class_names)))

    # Calculating and ploting Confusion Matrix
    # cm = confusion_matrix(all_preds, all_tests)
#        print('Confusion matrix:\n%s' % cm)

    # plt.figure()
    # plot_confusion_matrix(cm, class_names, title='Confusion matrix, without normalization')

    # plt.figure()
    # plot_confusion_matrix(cm, class_names, normalize=True, title='Normalized confusion matrix')


    # sgan.evaluate_discriminator(X_test, y_test)
    # sgan.predict(X_test, y_test)

@cli.command()
@click.option('-d', type=click.Path(exists=True),
    help='Directory to read images from')
@click.option('-n', type=int, default=500,
    help='Number of images in the sample')
@click.option('-o', 'output', default='output',
    help='Output Folder')
def create_dataset(d, n, output):
    prefixes = [d + '/' + p.split('.')[0] for p in os.listdir(d) if '_' not in p and 'tif' in p]
    prefixes = np.random.choice(prefixes, n, replace=False)
    out_path = output + '/out'
    if os.path.isfile(out_path):
        os.remove(out_path)

    m = mmappickle.mmapdict(out_path)
    for prefix in prefixes:
        crop, cells = image_for_prefix(prefix)
        d = {
            'crop': crop,
            'cell': cells
        }

        key = os.path.basename(prefix)
        m[key] = d

if __name__ == '__main__':
    cli()