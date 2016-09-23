import pickle
import matplotlib.pyplot as plt
from scipy.misc import imread
from sklearn.metrics import accuracy_score
from segmentation_scoring import rejectOne_score, dice
from sklearn import preprocessing
import os
from tabulate import tabulate
from os.path import dirname, abspath


def visualize_learning(model_path, model_restored_path = None, start_visu=0):
    """
    :param model_path: path of the folder including the model parameters .ckpt
    :param model_restored_path: if the model is initialized by another, path of its folder
    :param start_visu: first iterations can reach extreme values, start_visu set the start of the visualization
    :return: no return

    figure(1) represent the evolution of the loss and the accuracy evaluated on the test set along the learning process
    figure(2) if learning initialized by another, merging of the two representations

    """

    current_path = dirname(abspath(__file__))
    parent_path = dirname(current_path)

    folder_model = model_path

    folder_restored_model = model_restored_path

    file = open(folder_model+'/evolution.pkl','r') # learning variables : loss, accuracy, epoch
    evolution = pickle.load(file)

    if model_restored_path:
        file_restored = open(folder_restored_model+'/evolution.pkl','r')
        evolution_restored = pickle.load(file_restored)
        last_epoch = evolution_restored['steps'][-1]

        evolution_merged = {}
        for key in ['steps','accuracy','loss'] :
            evolution_merged[key] = evolution_restored[key]+evolution[key]

        fig = plt.figure(1)
        ax = fig.add_subplot(111)
        ax.plot(evolution_merged['steps'][start_visu:], evolution_merged['accuracy'][start_visu:], '-', label = 'accuracy')
        plt.ylabel('Accuracy')
        plt.ylim(ymin = 0.7)
        ax2 = ax.twinx()
        ax2.axvline(last_epoch, color='k', linestyle='--')
        plt.title('Evolution merged (before and after restauration')
        ax2.plot(evolution_merged['steps'][start_visu:], evolution_merged['loss'][start_visu:], '-r', label = 'loss')
        plt.ylabel('Loss')
        plt.ylim(ymax = 100)
        plt.xlabel('Epoch')

    fig = plt.figure(2)
    ax = fig.add_subplot(111)
    ax.plot(evolution['steps'][start_visu:], evolution['accuracy'][start_visu:], '-', label = 'accuracy')
    plt.ylabel('Accuracy')
    plt.ylim(ymin = 0.7)
    ax2 = ax.twinx()
    plt.title('Accuracy and loss evolution')
    ax2.plot(evolution['steps'][start_visu:], evolution['loss'][start_visu:], '-r', label = 'loss')
    plt.ylabel('Loss')
    plt.ylim(ymax = 100)
    plt.xlabel('Epoch')
    plt.show()



def visualize_results(path) :
    """
    :param path: path of the folder including the data and the results obtained after by the segmentation process.
    :return: no return
    if there is a mask (ground truth) in the folder, scores are calculated : sensitivity, errors and dice
    figure(1) segmentation without mrf
    figure(2) segmentation with mrf
    if there is myelin.jpg in the folder, myelin and image, myelin and axon segmentated, myelin and groundtruth are represented
    """

    path_img = path+'/image.jpg'
    Mask = False

    if not 'results.pkl' in os.listdir(path):
        print 'results not present'

    file = open(path+'/results.pkl','r')
    res = pickle.load(file)

    img_mrf = res['img_mrf']
    prediction = res['prediction']
    image_init = imread(path_img, flatten=False, mode='L')


    plt.figure(1)
    plt.title('With MRF')
    plt.imshow(image_init, cmap=plt.get_cmap('gray'))
    plt.hold(True)
    plt.imshow(img_mrf, alpha=0.7)


    plt.figure(2)
    plt.title('Without MRF')
    plt.imshow(image_init, cmap=plt.get_cmap('gray'))
    plt.hold(True)
    plt.imshow(prediction, alpha=0.7)

    if 'mask.jpg' in os.listdir(path):
        Mask = True
        path_mask = path+'/mask.jpg'
        mask = preprocessing.binarize(imread(path_mask, flatten=False, mode='L'), threshold=125)

        acc = accuracy_score(prediction.reshape(-1,1), mask.reshape(-1,1))
        score = rejectOne_score(image_init, mask.reshape(-1, 1), prediction.reshape(-1,1), visualization=False, min_area=1, show_diffusion = True)
        Dice = dice(image_init, mask.reshape(-1, 1), prediction.reshape(-1,1))['dice'].mean()
        acc_mrf = accuracy_score(img_mrf.reshape(-1, 1), mask.reshape(-1, 1))
        score_mrf = rejectOne_score(image_init, mask.reshape(-1,1), img_mrf.reshape(-1,1), visualization=False, min_area=1, show_diffusion = True)
        Dice_mrf = dice(image_init, mask.reshape(-1, 1), img_mrf.reshape(-1,1))['dice'].mean()

        headers = ["MRF", "accuracy", "sensitivity", "errors", "diffusion", "Dice"]
        table = [["False", acc, score[0], score[1], score[2], Dice],
        ["True", acc_mrf, score_mrf[0], score_mrf[1], score_mrf[2], Dice_mrf]]

        subtitle2 = '\n\n---Scores---\n\n'
        scores = tabulate(table, headers)
        text = subtitle2+scores
        print text

        file = open(path+"/Report_results.txt", 'w')
        file.write(text)
        file.close()

    if 'myelin.jpg' in os.listdir(path):
        path_myelin = path + '/myelin.jpg'
        myelin = preprocessing.binarize(imread(path_myelin, flatten=False, mode='L'), threshold=125)


        plt.figure(3)
        plt.title('Myelin')
        plt.imshow(image_init, cmap=plt.get_cmap('gray'))
        plt.hold(True)
        plt.imshow(myelin, alpha=0.7)

        plt.figure(4)
        plt.title('Myelin - Axon')
        plt.imshow(img_mrf, cmap=plt.get_cmap('gray'))
        plt.hold(True)
        plt.imshow(myelin, alpha=0.7)

        if Mask :
            plt.figure(5)
            plt.title('Myelin - GroundTruth')
            plt.imshow(mask, cmap=plt.get_cmap('gray'))
            plt.hold(True)
            plt.imshow(myelin, alpha=0.7)

    plt.show()
