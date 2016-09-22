import numpy as np
from scipy.ndimage.filters import gaussian_filter
import scipy
import math
from evaluation.segmentation_scoring import rejectOne_score
from sklearn.metrics import accuracy_score
import copy
import os
import pickle
from tabulate import tabulate
from config import*

def mrf_map(X, Y, mu, sigma, nb_class, max_map_iter, alpha, beta):
    """
        Goal:       Run the MRF_MAP_ICM process
        Input:      - X = labels
                    - Y = extracted features
                    - nb_class
                    - max_map_iter = maximum number of iteration to run
                    - alpha = weight of the unary potential function
                    - beta = weight of the pairwise potential function
        Output:     Regularized label field
    """
    im_x, im_y = Y.shape[:2]
    y = Y.reshape((-1,1))
    global_nrj = np.zeros((im_x * im_y, nb_class))
    sum_nrj_map = []
    neigh_mask = beta * np.asarray([[0, 1, 0], [1, 0, 1], [0, 1, 0]])

    for it in range(max_map_iter):
        unary_nrj = np.copy(global_nrj)
        pairwise_nrj = np.copy(global_nrj)

        for l in range(nb_class):
            yi = y - mu[l]
            temp1 = (yi * yi) / (2 * np.square(sigma[l])) + math.log(sigma[l])
            unary_nrj[:, l] = unary_nrj[:, l] + temp1[:, 0]

            label_mask = np.zeros(X.shape)
            label_mask[np.where(X == l)] = 1
            pairwise_nrj_temp = scipy.ndimage.convolve(label_mask, neigh_mask, mode='constant')
            pairwise_nrj_temp *= -1.0
            pairwise_nrj[:, l] = pairwise_nrj_temp.flat

        global_nrj = np.copy(alpha * unary_nrj + pairwise_nrj)
        X = np.copy(np.argmin(global_nrj, axis=1).reshape((im_x, im_y)))

        sum_nrj_map.append(np.sum(np.amin(global_nrj, axis=1).reshape((-1, 1))))
        if it >= 3 and np.std(sum_nrj_map[it-2:it])/np.absolute(sum_nrj_map[it]) < 0.01:
            break

    return X

def run_mrf(label_field, feature_field, nb_class, max_map_iter, weight):
    """
        Goal:       Run the MRF_MAP_ICM process
        Input:      - label_field = SVM outputted labels
                    - feature_field = extracted features
                    - nb_class
                    - max_map_iter = maximum number of iteration to run
                    - weight = weights
        Output:     Regularized label field
    """
    img_shape = feature_field.shape
    mu = []
    sigma = []

    blurred = gaussian_filter(feature_field, sigma=weight[2])
    y = blurred.reshape((-1,1))

    for i in range(nb_class):
        yy = y[np.where(label_field == i)[0], 0]
        mu.append(np.mean(yy))
        sigma.append(np.std(yy))

    X = label_field.reshape(img_shape)
    X = X.astype(int)
    Y = blurred

    return mrf_map(X, Y, mu, sigma, nb_class, max_map_iter, weight[0], weight[1])


def train_mrf(label_fields, feature_fields, nb_class, max_map_iter, weight, threshold_learning, labels_true, threshold_sensitivity, threshold_error=1.0):
    """
        Goal:       Weight Learning by maximizing the pixel accuracy + sensitivity condition
        Input:      - label_field = SVM outputted labels
                    - feature_field = extracted features
                    - nb_class
                    - max_map_iter = maximum number of iteration to run
                    - weight = weight initialization
                    - threshold_learning = learning rate
                    - label_true = ground true
                    - threshold_sensitivity = condition on the sensitivity
                    - threshold_error = condition on the 'error'
        Output:     - weight[0] = weight of the unary potential function
                    - weight[1] = weight of the pairwise potential function
                    - weight[2] = standard deviation for Gaussian kernel
    """
    s = [1] * len(weight)
    d = [1] * len(weight)

    weight_init = copy.deepcopy(weight)

    best_score_list = []
    for label_field, feature_field, label_true in zip(label_fields, feature_fields, labels_true):
        res = run_mrf(label_field, feature_field, nb_class, max_map_iter, weight)
        best_score_list.append(accuracy_score(label_true, res.reshape((-1, 1))))
    best_score = np.mean(best_score_list)

    while any(ss >= threshold_learning for ss in s):
        for i in range(len(weight)):
            weight_cur = copy.deepcopy(weight)
            weight_cur[i] = weight[i] + s[i] * d[i]

            acc_mrf_list = []
            scores_0_list = []
            scores_1_list = []
            for label_field, feature_field, label_true in zip(label_fields, feature_fields, labels_true):
                res = run_mrf(label_field, feature_field, nb_class, max_map_iter, weight_cur)
                acc_mrf_list.append(accuracy_score(label_true, res.reshape((-1, 1))))
                scores_0_list.append(rejectOne_score(feature_field, label_true, res.reshape((-1,1)), visualization=False, show_diffusion=True, min_area = 0)[0])
                scores_1_list.append(rejectOne_score(feature_field, label_true, res.reshape((-1,1)), visualization=False, show_diffusion=True, min_area = 0)[1])
            acc_mrf = np.mean(acc_mrf_list)
            scores_0 = np.mean(scores_0_list)
            scores_1 = np.mean(scores_1_list)

            if acc_mrf > best_score and scores_0 > threshold_sensitivity and scores_1 < threshold_error:
                best_score = acc_mrf
                weight[i] = weight_cur[i]

            else:
                s[i] = float(s[i])/2
                d[i] = -d[i]

    print 'Learned parameters: ' + str(weight)
    print 'Learned parameters: ' + str(weight_init)
    print ' \n'
    if cmp(weight_init, weight) == 0:
        print 'No parameter changes: re-examine the learning conditions'

    return weight


def learn_mrf(image_paths, model_path, mrf_path):
    """
    :param image_path : folder of the data to train the mrf, must include image.jpg
    :param model_path : folder of the model to bring an initial segmentation
    :param mrf_path : folder to put the weights learned for the mrf
    :return: no return

    Weights are saved in mrf_parameter.pkl
    Scores are printed after the training

    """

    from apply_model import apply_convnet
    from sklearn import preprocessing
    from skimage.transform import rescale
    from scipy.misc import imread


    nb_class = 2
    max_map_iter = 10
    alpha = 1.0
    beta = 1.0
    sigma_blur = 1.0
    threshold_learning = 0.1
    threshold_sensitivity = 0.55
    threshold_error = 0.15


    folder_mrf = mrf_path
    if not os.path.exists(folder_mrf):
        os.makedirs(folder_mrf)

    images_init = []
    label_fields = []
    labels_true = []
    for image_path in image_paths :

        path_img = image_path+'/image.jpg'
        path_mask = image_path+'/mask.jpg'

        file = open(image_path+'/pixel_size_in_micrometer.txt', 'r')
        pixel_size = float(file.read())
        rescale_coeff = pixel_size/general_pixel_size

        images_init.append((rescale(imread(path_img, flatten=False, mode='L'), rescale_coeff)*256).astype(int))

        mask = preprocessing.binarize((rescale(imread(path_mask, flatten=False, mode='L'))*256).astype(int), threshold=125)

        labels_true.append(mask.reshape(-1,1))

        prediction = apply_convnet(image_path, model_path)
        label_fields.append(prediction.reshape(-1, 1))

    weight = train_mrf(label_fields, images_init, nb_class, max_map_iter, [alpha, beta, sigma_blur], threshold_learning, labels_true, threshold_sensitivity)

    mrf_coef = {'weight': weight, "nb_class": nb_class, 'max_map_iter': max_map_iter, 'alpha': alpha, 'beta': beta,
                'sigma_blur': sigma_blur, 'threshold_error': threshold_error,
                'threshold_sensitivity': threshold_sensitivity, 'threshold_learning': threshold_learning}

    with open(folder_mrf+'/mrf_parameter.pkl', 'wb') as handle:
         pickle.dump(mrf_coef, handle)


    acc_list = []
    acc_mrf_list = []

    score_0_list = []
    score_1_list = []
    score_2_list = []

    score_0_mrf_list = []
    score_1_mrf_list = []
    score_2_mrf_list = []

    for label_field, image_init, label_true,image_path in zip(label_fields, images_init, labels_true, image_paths):
        img_mrf = run_mrf(label_field, image_init, nb_class, max_map_iter, weight)
        img_mrf = img_mrf == 1

    #-----Results------

        acc_list.append(accuracy_score(label_field, label_true))
        acc_mrf_list.append(accuracy_score(img_mrf.reshape(-1, 1), label_true))

        score = rejectOne_score(image_init, label_true, label_field, visualization=False, min_area=1, show_diffusion = True)
        score_0_list.append((score)[0])
        score_1_list.append(score[1])
        score_2_list.append(score[2])

        score_mrf = rejectOne_score(image_init, label_true, img_mrf.reshape(-1,1), visualization=False, min_area=1, show_diffusion = True)
        score_0_mrf_list.append(score_mrf[0])
        score_1_mrf_list.append(score_mrf[1])
        score_2_mrf_list.append(score_mrf[2])


    subtitle_1 = '\n\n\n---Parameters---\n'
    parameters= '\n threshold_learning :%s'%(threshold_learning)
    parameters+= '\n threshold_error :%s'%(threshold_error)
    parameters+= '\n threshold_error :%s'%(threshold_sensitivity)

    subtitle_2 = '\n\n\n---Average scores on the training images : ' + str(image_paths) + '\n\n'
    headers = ["MRF", "accuracy", "sensitivity", "errors", "diffusion"]
    table = [["False", np.mean(acc_list), np.mean(score_0_list), np.mean(score_1_list),  np.mean(score_2_list)],
    ["True", np.mean(acc_mrf_list), np.mean(score_0_mrf_list), np.mean(score_1_mrf_list), np.mean(score_2_mrf_list)]]

    scores = tabulate(table, headers)
    Report = subtitle_1 + parameters + subtitle_2 + scores

    file = open(folder_mrf+"/report_mrf.txt", 'w')
    file.write(Report)
    file.close()





