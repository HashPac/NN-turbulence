import numpy as np
from nn import NN
from core import Core
from keras.models import Sequential
from keras.layers import Dense, Lambda
from keras.callbacks import EarlyStopping
from sklearn.utils import shuffle
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import keras.backend as K
import math as m
import matplotlib.pyplot as plt


def make_realizable(labels):

        numPoints = labels.shape[0]
        A = np.zeros((3, 3))

        for i in range(numPoints):
            # Scales all on-diags to retain zero trace
            if np.min(labels[i, [0, 4, 8]]) < -1./3.:
                labels[i, [0, 4, 8]] *= -1./(3.*np.min(labels[i, [0, 4, 8]]))
            if 2.*np.abs(labels[i, 1]) > labels[i, 0] + labels[i, 4] + 2./3.:
                labels[i, 1] = (labels[i, 0] + labels[i, 4] + 2./3.)*.5*np.sign(labels[i, 1])
                labels[i, 3] = (labels[i, 0] + labels[i, 4] + 2./3.)*.5*np.sign(labels[i, 1])
            if 2.*np.abs(labels[i, 5]) > labels[i, 4] + labels[i, 8] + 2./3.:
                labels[i, 5] = (labels[i, 4] + labels[i, 8] + 2./3.)*.5*np.sign(labels[i, 5])
                labels[i, 7] = (labels[i, 4] + labels[i, 8] + 2./3.)*.5*np.sign(labels[i, 5])
            if 2.*np.abs(labels[i, 2]) > labels[i, 0] + labels[i, 8] + 2./3.:
                labels[i, 2] = (labels[i, 0] + labels[i, 8] + 2./3.)*.5*np.sign(labels[i, 2])
                labels[i, 6] = (labels[i, 0] + labels[i, 8] + 2./3.)*.5*np.sign(labels[i, 2])

            # Enforce positive semidefinite by pushing evalues to non-negative
            A[0, 0] = labels[i, 0]
            A[1, 1] = labels[i, 4]
            A[2, 2] = labels[i, 8]
            A[0, 1] = labels[i, 1]
            A[1, 0] = labels[i, 1]
            A[1, 2] = labels[i, 5]
            A[2, 1] = labels[i, 5]
            A[0, 2] = labels[i, 2]
            A[2, 0] = labels[i, 2]
            evalues, evectors = np.linalg.eig(A)
            if np.max(evalues) < (3.*np.abs(np.sort(evalues)[1])-np.sort(evalues)[1])/2.:
                evalues = evalues*(3.*np.abs(np.sort(evalues)[1])-np.sort(evalues)[1])/(2.*np.max(evalues))
                A = np.dot(np.dot(evectors, np.diag(evalues)), np.linalg.inv(evectors))
                for j in range(3):
                    labels[i, j] = A[j, j]
                labels[i, 1] = A[0, 1]
                labels[i, 5] = A[1, 2]
                labels[i, 2] = A[0, 2]
                labels[i, 3] = A[0, 1]
                labels[i, 7] = A[1, 2]
                labels[i, 6] = A[0, 2]
            if np.max(evalues) > 1./3. - np.sort(evalues)[1]:
                evalues = evalues*(1./3. - np.sort(evalues)[1])/np.max(evalues)
                A = np.dot(np.dot(evectors, np.diag(evalues)), np.linalg.inv(evectors))
                for j in range(3):
                    labels[i, j] = A[j, j]
                labels[i, 1] = A[0, 1]
                labels[i, 5] = A[1, 2]
                labels[i, 2] = A[0, 2]
                labels[i, 3] = A[0, 1]
                labels[i, 7] = A[1, 2]
                labels[i, 6] = A[0, 2]

        return labels


def plot_results(predicted_stresses, true_stresses):

    fig = plt.figure()
    fig.patch.set_facecolor('white')
    on_diag = [0, 4, 8]
    for i in range(9):
            plt.subplot(3, 3, i+1)
            ax = fig.gca()
            ax.set_aspect('equal')
            plt.plot([-1., 1.], [-1., 1.], 'r--')
            plt.scatter(true_stresses[:, i], predicted_stresses[:, i])
            plt.xlabel('True value')
            plt.ylabel('Predicted value')
            if i in on_diag:
                plt.xlim([-1./3., 2./3.])
                plt.ylim([-1./3., 2./3.])
            else:
                plt.xlim([-0.5, 0.5])
                plt.ylim([-0.5, 0.5])
    plt.show()


def main():
    Retau = 180
    RA_list = [1,3,5,7,10,14]
    velocity_comps = ['U', 'V', 'W']
    DIM = len(velocity_comps)
    predict_index = 1

    print('--> Build network')
    nodes = 30
    layers = 8

    eigenvalues_shape = 6
    tensorbasis_shape = 10
    stresstensor_shape = 9

    core = Core()
    neural_network = NN(layers, nodes, eigenvalues_shape, tensorbasis_shape, stresstensor_shape)
    neural_network.build()

    RA_list_loop = []
    for i,x in enumerate(RA_list):
        if i!= predict_index:
            RA_list_loop.append(x)

    # Loop over multiple cases to train the network
    # Exclude one case, which can be used to predict
    for RA in RA_list[0:1]:
        usecase =  str(RA)+'_'+str(Retau)

        print('--> Import coordinate system for training')
        ycoord, DIM_Y = Core.importCoordinates('y', usecase)
        zcoord, DIM_Z = Core.importCoordinates('z', usecase)

        print('--> Import mean velocity field for training')
        data = np.zeros([DIM_Y, DIM_Z, DIM])
        for ii in range(DIM):
            data[:,:,ii] = core.importMeanVelocity(DIM_Y, DIM_Z, usecase, velocity_comps[ii])

        print('--> Compute mean velocity gradient for training')
        velocity_gradient = core.gradient(data, ycoord, zcoord)

        core.tensorplot(velocity_gradient, DIM_Y, DIM_Z, 'Velocity gradient')

        print('--> Import Reynolds stress tensor for training')
        stresstensor = core.importStressTensor(usecase, DIM_Y, DIM_Z)
        stresstensor = np.reshape(stresstensor, (-1, 3, 3))

        ############ Preparing network inputs #####################################

        print('--> Compute omega field for training')
        eps = 1*np.ones([DIM_Y, DIM_Z]) ## For now using epsilon=1 everywhere
        print('--> Compute k field for training')
        # k = core.calc_k(stresstensor) ## In realitiy this is not possible, because k is unknown
        k = 1*np.ones([DIM_Y, DIM_Z]) ## For now using k=1 everywhere
        k = np.reshape(k, (DIM_Y, DIM_Z))
        print('--> Compute rotation rate and strain rate tensors for training')
        S,R = core.calc_S_R(velocity_gradient, k, eps)
        print('--> Compute eigenvalues for network input for training')
        eigenvalues = core.calc_scalar_basis(S, R)  # Scalar basis lamba's
        print('--> Compute tensor basis for training')
        tensorbasis = core.calc_tensor_basis(S, R)

        # Plot tensorbasis
        #for x in range(0,10):
        #    core.tensorplot(tensorbasis[:,:,x], DIM_Y, DIM_Z, str(x))

        core.tensorplot(S[:,:,:,:], DIM_Y, DIM_Z, 'Strain rate tensor')
        core.tensorplot(R[:,:,:,:], DIM_Y, DIM_Z, 'Rotation rate tensor')

        ## Reshape 2D array to 1D arrays. Network only takes 1D arrays
        k = np.reshape(k, -1)
        #b = core.calc_output(stresstensor, k)
        stresstensor = np.reshape(stresstensor, (-1, 9))
        tensorbasis = np.reshape(tensorbasis, (-1, 10, 9))
        eigenvalues = np.reshape(eigenvalues, (-1, 6))

        print('--> Train network')
        neural_network.train(eigenvalues, tensorbasis, stresstensor)

    # Predict stresstensor using case not used in training
    RA = RA_list[predict_index]
    usecase =  str(RA)+'_'+str(Retau)

    print('--> Import coordinate system for predicting')
    ycoord, DIM_Y = Core.importCoordinates('y', usecase)
    zcoord, DIM_Z = Core.importCoordinates('z', usecase)

    print('--> Import mean velocity field for predicting')
    data = np.zeros([DIM_Y, DIM_Z, DIM])
    for ii in range(DIM):
        data[:,:,ii] = core.importMeanVelocity(DIM_Y, DIM_Z, usecase, velocity_comps[ii])

    print('--> Compute mean velocity gradient for predicting')
    velocity_gradient = core.gradient(data, ycoord, zcoord)

    ############ Preparing network inputs #####################################

    print('--> Compute omega field for predicting')
    eps = 1*np.ones([DIM_Y, DIM_Z]) ## For now using epsilon=1 everywhere
    print('--> Compute k field')
    # k = core.calc_k(stresstensor) ## In realitiy this is not possible, because k is unknown
    k = 1*np.ones([DIM_Y, DIM_Z]) ## For now using k=1 everywhere
    k = np.reshape(k, (DIM_Y, DIM_Z))
    print('--> Compute rotation rate and strain rate tensors for predicting')
    S,R = core.calc_S_R(velocity_gradient, k, eps)
    print('--> Compute eigenvalues for network input for predicting')
    eigenvalues = core.calc_scalar_basis(S, R)  # Scalar basis lamba's
    print('--> Compute tensor basis for predicting')
    tensorbasis = core.calc_tensor_basis(S, R)

    #core.tensorplot(S[:,:,:,:], DIM_Y, DIM_Z, 'Strain rate tensor')
    #core.tensorplot(R[:,:,:,:], DIM_Y, DIM_Z, 'Rotation rate tensor')

    ## Reshape 2D array to 1D arrays. Network only takes 1D arrays
    k = np.reshape(k, -1)
    tensorbasis = np.reshape(tensorbasis, (-1, 10, 9))
    eigenvalues = np.reshape(eigenvalues, (-1, 5))

    print('--> Build network')
    neural_network = NN(8, 30, eigenvalues.shape[1], tensorbasis.shape[1], b.shape[1])
    neural_network.build()


    print('--> Train network')
    prediction = neural_network.train(eigenvalues, tensorbasis, b)

    # for i in range(5):
    #     prediction = make_realizable(prediction)

    print('--> Plot b prediction')
    plot_results(prediction, b)

    print('--> Plot stress tensor')
    # stresstensor = core.calc_tensor(b, k)
    core.tensorplot(stresstensor, DIM_Y, DIM_Z)
    predicted_stress = core.calc_tensor(prediction, k)
    core.tensorplot(predicted_stress, DIM_Y, DIM_Z)

    plt.show()

main()
