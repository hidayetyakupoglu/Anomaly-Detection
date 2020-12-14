# Author：MaXiao
# E-mail：maxiaoscut@aliyun.com
# Github：https://github.com/Albertsr

import time
import numpy as np
from sklearn.decomposition import KernelPCA
from sklearn.preprocessing import StandardScaler


class KPCA_Recon_Error:
    """Implementation of anomaly detection base on KernelPCA reconstruction error."""
    def __init__(self, matrix, contamination=0.01, kernel='rbf', verbose=3, gamma=None, random_state=2018):
        
        '''
        Parameters
        --------------------------
        :param matrix : dataset, shape = [n_samples, n_features]
        
        :param contamination : float, should be in the range [0, 0.5], default=0.01
              The amount of contamination of the data set, i.e. the proportion of outliers in the data set. 
              Used when fitting to define the threshold on the scores of the samples.
              
        :param kernel : 'linear' | 'poly' | 'rbf' | 'sigmoid' | 'cosine' | 'precomputed', default='rbf'.
        
        :param verbose: int, default=3, Verbosity mode. the higher, the less messages.
              the matrix reconstruction of KernelPCA is time-consuming, this parameter helps to check 
              the progress of the reconstruction. If verbose = m, process information is printed every m rounds.
              
        :param gamma : float, default=1/n_features
             Kernel coefficient for rbf, poly and sigmoid kernels. Ignored by other kernels.
        '''
        self.matrix = StandardScaler().fit_transform(matrix)
        self.contamination = contamination
        self.kernel = kernel
        self.gamma = gamma
        self.verbose = verbose
        self.random_state = random_state
    
    def get_ev_ratio(self):
        transformer = KernelPCA(n_components=None, kernel=self.kernel, gamma=self.gamma,
            fit_inverse_transform=True, random_state=self.random_state, n_jobs=-1)
        transformer.fit_transform(self.matrix) 
        # ev_ratio is the cumulative proportion of eigenvalues and the weight of 
        # reconstruction error corresponding to different number of principal components
        ev_ratio = np.cumsum(transformer.lambdas_) / np.sum(transformer.lambdas_)
        return ev_ratio
    
    def reconstruct_matrix(self):
        # the parameter recon_pc_num is the number of top principal components used in the reconstruction matrix.
        def reconstruct(recon_pc_num):  
            transformer = KernelPCA(n_components=recon_pc_num, kernel=self.kernel, gamma=self.gamma, 
                fit_inverse_transform=True, n_jobs=-1, random_state=self.random_state)
            X_transformed = transformer.fit_transform(self.matrix)
            recon_matrix = transformer.inverse_transform(X_transformed)
            assert_description = 'The shape of the reconstruction matrix should be equal to that of the initial matrix.'
            assert recon_matrix.shape == self.matrix.shape, assert_description
            return recon_matrix
        
        # generating a series of reconstruction matrices
        # the matrix reconstruction of KernelPCA is time-consuming, and the parameter verbose helps to check 
        # the progress of the reconstruction, process information is printed every verbose rounds.
        cols_num = self.matrix.shape[1]
        if not self.verbose:
            recon_matrices = [reconstruct(i) for i in range(1, cols_num+1)]
        else:
            recon_matrices = []
            time_cost = 0
            start = time.time()
            for i in range(1, cols_num+1):
                recon_matrices.append(reconstruct(i))
                if i % int(self.verbose) == 0:
                    running_time = time.time()-start
                    time_cost += running_time
                    print('{} feature(s) participate in reconstruction, running time: {:.2f}s'.format(i, running_time))
                    start = time.time()
                if i == cols_num:
                    running_time = time.time()-start
                    time_cost += running_time
                    print('A total of {} matrices have been reconstructed, total time: {:.2f}s'.format(cols_num, time_cost))
         
        # randomly select two reconstruction matrices to verify that they are different
        i, j = np.random.choice(range(cols_num), size=2, replace=False)
        description = 'The reconstruction matrices generated by different number of principal components are different.'
        assert not np.all(recon_matrices[i] == recon_matrices[j]), description
        return recon_matrices
        
    def get_anomaly_score(self):
        # calculate the modulus of a vector
        def compute_vector_length(vector):
            square_sum = np.square(vector).sum()
            return np.sqrt(square_sum)
        
        # calculate the anomaly score generated by a single reconstruction matrix for all samples
        def compute_sub_score(recon_matrix, ev):
            delta_matrix = self.matrix - recon_matrix
            score = np.apply_along_axis(compute_vector_length, axis=1, arr=delta_matrix) * ev
            return score
        
        ev_ratio = self.get_ev_ratio()
        reconstruct_matrices = self.reconstruct_matrix()
        # summarize the anomaly scores generated by all reconstruction matrices
        anomaly_scores = list(map(compute_sub_score, reconstruct_matrices, ev_ratio))
        return np.sum(anomaly_scores, axis=0)

    # returns indices with the highest anomaly score based on a specific contamination
    def get_anomaly_indices(self):
        indices_desc = np.argsort(-self.get_anomaly_score())
        anomaly_num = int(np.ceil(len(self.matrix) * self.contamination))
        anomaly_indices = indices_desc[:anomaly_num]
        return anomaly_indices
    
    # returns 1 if the prediction is an anomaly, otherwise returns 0
    def predict(self):
        anomaly_indices = self.get_anomaly_indices()
        pred_result = np.isin(range(len(self.matrix)), anomaly_indices).astype(int)
        return pred_result
