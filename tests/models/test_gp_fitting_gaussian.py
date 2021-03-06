import unittest

import numpy as np
import numpy.testing as npt

from copy import deepcopy

from stratified_bayesian_optimization.models.gp_fitting_gaussian import (
    GPFittingGaussian,
    ValidationGPModel,
)
from stratified_bayesian_optimization.lib.constant import (
    MATERN52_NAME,
    SMALLEST_POSITIVE_NUMBER,
    CHOL_COV,
    SOL_CHOL_Y_UNBIASED,
    TASKS_KERNEL_NAME,
    PRODUCT_KERNELS_SEPARABLE,
    SCALED_KERNEL,
)
from stratified_bayesian_optimization.lib.finite_differences import FiniteDifferences
from stratified_bayesian_optimization.lib.sample_functions import SampleFunctions
from stratified_bayesian_optimization.kernels.matern52 import Matern52
from stratified_bayesian_optimization.kernels.scaled_kernel import ScaledKernel


class TestGPFittingGaussian(unittest.TestCase):

    def setUp(self):
        type_kernel = [SCALED_KERNEL, MATERN52_NAME]
        self.training_data = {
            "evaluations":
                [42.2851784656, 72.3121248508, 1.0113231069, 30.9309246906, 15.5288331909],
            "points": [
                [42.2851784656], [72.3121248508], [1.0113231069], [30.9309246906], [15.5288331909]],
            "var_noise": []}
        dimensions = [1]

        self.gp = GPFittingGaussian(type_kernel, self.training_data, dimensions,
                                    bounds_domain=[[0, 100]])

        self.training_data_3 = {
            "evaluations": [42.2851784656, 72.3121248508, 1.0113231069, 30.9309246906,
                            15.5288331909],
            "points": [
                [42.2851784656], [72.3121248508], [1.0113231069], [30.9309246906], [15.5288331909]],
            "var_noise": [0.5, 0.8, 0.7, 0.9, 1.0]}

        self.gp_3 = GPFittingGaussian(type_kernel, self.training_data_3, dimensions,
                                      bounds_domain=[[0, 100]])
        self.training_data_simple = {
            "evaluations": [5],
            "points": [[5]],
            "var_noise": []}
        dimensions = [1]

        self.simple_gp = GPFittingGaussian(type_kernel, self.training_data_simple, dimensions,
                                           bounds_domain=[[0, 100]])

        self.training_data_complex = {
            "evaluations": [1.0],
            "points": [[42.2851784656, 0]],
            "var_noise": [0.5]}

        self.complex_gp = GPFittingGaussian(
            [PRODUCT_KERNELS_SEPARABLE, MATERN52_NAME, TASKS_KERNEL_NAME],
            self.training_data_complex, [2, 1, 1], bounds_domain=[[0, 100], [0]])

        self.training_data_complex_2 = {
            "evaluations": [1.0, 2.0, 3.0],
            "points": [[42.2851784656, 0], [10.532, 0], [9.123123, 1]],
            "var_noise": [0.5, 0.2, 0.1]}

        self.complex_gp_2 = GPFittingGaussian(
            [PRODUCT_KERNELS_SEPARABLE, MATERN52_NAME, TASKS_KERNEL_NAME],
            self.training_data_complex_2, [3, 1, 2], bounds_domain=[[0, 100], [0, 1]])

        self.new_point = np.array([[80.0]])
        self.evaluation = np.array([80.0])

        self.training_data_noisy = {
            "evaluations": [41.0101845096],
            "points": [[42.2851784656]],
            "var_noise": [0.0181073779]}

        self.gp_noisy = GPFittingGaussian(type_kernel, self.training_data_noisy, dimensions,
                                          bounds_domain=[[0, 100]])

        np.random.seed(2)
        n_points = 50
        normal_noise = np.random.normal(0, 0.5, n_points)
        points = np.linspace(0, 500, n_points)
        points = points.reshape([n_points, 1])
        kernel = Matern52.define_kernel_from_array(1, np.array([100.0, 1.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]

        evaluations = function + normal_noise

        self.training_data_gp = {
            "evaluations": list(evaluations),
            "points": points,
            "var_noise": []}

        self.gp_gaussian = GPFittingGaussian([SCALED_KERNEL, MATERN52_NAME], self.training_data_gp,
                                             [1])

        self.gp_gaussian_2 = GPFittingGaussian([MATERN52_NAME], self.training_data_gp, [1],
                                               bounds_domain=[[0, 100]])

        self.training_data_gp_2 = {
            "evaluations": list(evaluations - 10.0),
            "points": points,
            "var_noise": []}
        self.gp_gaussian_central = GPFittingGaussian([SCALED_KERNEL, MATERN52_NAME],
                                                     self.training_data_gp_2, [1],
                                                     bounds_domain=[[0, 100]])

    def test_add_points_evaluations(self):

        self.gp.add_points_evaluations(self.new_point, self.evaluation)
        assert np.all(self.gp.data['evaluations'] == np.concatenate(
            (self.training_data['evaluations'], [80.0])))
        assert np.all(self.gp.data['points'] == np.concatenate(
            (self.training_data['points'], [[80.0]])))
        assert self.gp.data['var_noise'] is None

        assert self.gp.training_data == self.training_data

        self.gp_noisy.add_points_evaluations(self.new_point, self.evaluation, np.array([0.00001]))

        assert np.all(self.gp_noisy.data['evaluations'] == np.concatenate(
            (self.training_data_noisy['evaluations'], [80.0])))
        assert np.all(self.gp_noisy.data['points'] == np.concatenate(
            (self.training_data_noisy['points'], [[80.0]])))
        assert np.all(self.gp_noisy.data['var_noise'] == np.concatenate(
            (self.training_data_noisy['var_noise'], [0.00001])))

        assert self.gp_noisy.training_data == self.training_data_noisy

    def test_convert_from_list_to_numpy(self):
        data = GPFittingGaussian.convert_from_list_to_numpy(self.training_data_noisy)
        assert np.all(data['points'] == np.array([[42.2851784656]]))
        assert data['evaluations'] == np.array([41.0101845096])
        assert data['var_noise'] == np.array([0.0181073779])

        data_ = GPFittingGaussian.convert_from_list_to_numpy(self.training_data)
        assert np.all(data_['points'] == np.array(
            [[42.2851784656], [72.3121248508], [1.0113231069], [30.9309246906], [15.5288331909]]))
        assert np.all(data_['evaluations'] == np.array([42.2851784656, 72.3121248508, 1.0113231069,
                                                        30.9309246906, 15.5288331909]))
        assert data_['var_noise'] is None

    def test_convert_from_numpy_to_list(self):
        data = GPFittingGaussian.convert_from_list_to_numpy(self.training_data_noisy)
        data_list = GPFittingGaussian.convert_from_numpy_to_list(data)
        assert data_list == self.training_data_noisy

        data_ = GPFittingGaussian.convert_from_list_to_numpy(self.training_data)
        data_list_ = GPFittingGaussian.convert_from_numpy_to_list(data_)
        assert data_list_ == self.training_data

    def test_serialize(self):
        self.gp.add_points_evaluations(self.new_point, self.evaluation)
        dict = self.gp.serialize()

        n = len(self.training_data['points'])
        ls = np.mean([abs(self.training_data['points'][j][0] - self.training_data['points'][h][0])
                      for j in xrange(n) for h in xrange(n)]) / 0.324

        data = {
            "evaluations": [42.2851784656, 72.3121248508, 1.0113231069, 30.9309246906,
                            15.5288331909, 80.0],
            "points": [
                [42.2851784656], [72.3121248508], [1.0113231069], [30.9309246906], [15.5288331909],
                [80.0]],
            "var_noise": []
        }

        st_sampler = [592.54740339691523, 32.413676860959995, 83.633554944444455,
                      592.54740339691523]

        assert dict == {
            'type_kernel': [SCALED_KERNEL, MATERN52_NAME],
            'training_data': self.training_data,
            'dimensions': [1],
            'kernel_values': [ls, np.var(self.training_data['evaluations'])],
            'mean_value': [np.mean(self.training_data['evaluations'])],
            'var_noise_value': [np.var(self.training_data['evaluations'])],
            'thinning': 0,
            'data': data,
            "bounds_domain": [],
            'n_burning': 0,
            'max_steps_out': 1,
            'bounds_domain': [[0, 100]],
            'type_bounds': [0],
            'name_model': 'gp_fitting_gaussian',
            'problem_name': '',
            'training_name': '',
            'same_correlation': False,
            'start_point_sampler': st_sampler,
            'samples_parameters': dict['samples_parameters'],
        }

        gp = GPFittingGaussian([MATERN52_NAME], self.training_data, dimensions=[1])
        dict = gp.serialize()
        assert dict['bounds_domain'] == []

    def test_deserialize(self):
        params = {
            'type_kernel': [MATERN52_NAME],
            'training_data': self.training_data,
            'dimensions': [1],
        }
        gp = GPFittingGaussian.deserialize(params)

        assert gp.type_kernel == [MATERN52_NAME]
        assert gp.training_data == self.training_data
        assert gp.dimensions == [1]

    def test_get_parameters_model(self):
        parameters = self.gp.get_parameters_model
        parameters_values = [parameter.value for parameter in parameters]

        var = np.var(self.training_data['evaluations'])
        n = len(self.training_data['evaluations'])
        ls = np.mean([abs(self.training_data['points'][j][0] -
                          self.training_data['points'][h][0]) for j in xrange(n) for h in
                      xrange(n)]) / 0.324
        assert parameters_values[0] == var
        assert parameters_values[1] == np.mean(self.training_data['evaluations'])

        assert np.all(parameters_values[2] == ls)
        assert parameters_values[3] == var

    def test_get_value_parameters_model(self):
        var = np.var(self.training_data['evaluations'])
        mean = np.mean(self.training_data['evaluations'])

        n = len(self.training_data['evaluations'])
        ls = np.mean([abs(self.training_data['points'][j][0] -
                          self.training_data['points'][h][0]) for j in xrange(n) for h in
                      xrange(n)]) / 0.324
        parameters = self.gp.get_value_parameters_model
        assert np.all(parameters == np.array([var, mean, ls, var]))

    def test_cached_data(self):
        self.gp._updated_cached_data((3, 5, 1), -1, SOL_CHOL_Y_UNBIASED)
        assert self.gp.cache_sol_chol_y_unbiased[(3, 5, 1)] == -1
        assert self.gp.cache_sol_chol_y_unbiased.keys() == [(3, 5, 1)]
        assert self.gp._get_cached_data((3, 5, 1), SOL_CHOL_Y_UNBIASED) == -1

        self.gp._updated_cached_data((3, 5), 0, CHOL_COV)
        assert self.gp.cache_chol_cov[(3, 5)] == 0
        assert self.gp.cache_chol_cov.keys() == [(3, 5)]
        assert self.gp.cache_sol_chol_y_unbiased == {}
        assert self.gp._get_cached_data((3, 5), CHOL_COV) == 0

        assert self.gp._get_cached_data((3, 0), CHOL_COV) is False

    def test_chol_cov_including_noise(self):
        chol, cov = self.simple_gp._chol_cov_including_noise(1.0, np.array([1.0, 1.0]))
        assert cov == np.array([[2.0]])
        assert chol == np.array([[np.sqrt(2.0)]])

        chol, cov = self.simple_gp._chol_cov_including_noise(1.0, np.array([1.0, 1.0]))
        assert cov == np.array([[2.0]])
        assert chol == np.array([[np.sqrt(2.0)]])

        chol, cov = self.complex_gp._chol_cov_including_noise(1.0, np.array([1.0, 0.0]))
        assert cov == np.array([[2.5]])
        assert chol == np.array([[np.sqrt(2.5)]])

    def test_log_likelihood(self):
        llh = self.complex_gp.log_likelihood(1.0, 1.0, np.array([1.0, 0.0]))
        assert llh == -0.45814536593707761

    def test_grad_log_likelihood(self):
        grad = self.complex_gp_2.grad_log_likelihood(1.0, 1.0, np.array([1.0, 0.0, 0.0, 0.0]))

        dh = 0.0000001
        finite_diff = FiniteDifferences.forward_difference(
            lambda params: self.complex_gp_2.log_likelihood(
                params[0], params[1], params[2:]
            ),
            np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0]), np.array([dh]))

        for i in range(6):
            npt.assert_almost_equal(finite_diff[i], grad[i])

        grad_2 = self.complex_gp_2.grad_log_likelihood(1.82, 123.1,
                                                       np.array([5.0, 1.0, -5.5, 10.0]))

        dh = 0.00000001
        finite_diff_2 = FiniteDifferences.forward_difference(
            lambda params: self.complex_gp_2.log_likelihood(
                params[0], params[1], params[2:]
            ),
            np.array([1.82, 123.1, 5.0, 1.0, -5.5, 10.0]), np.array([dh]))

        for i in range(6):
            npt.assert_almost_equal(finite_diff_2[i], grad_2[i], decimal=3)

        grad_3 = self.gp_3.grad_log_likelihood(1.82, 123.1, np.array([5.0, 7.3]))
        dh = 0.0000001
        finite_diff_3 = FiniteDifferences.forward_difference(
            lambda params: self.gp_3.log_likelihood(
                params[0], params[1], params[2:]
            ),
            np.array([1.82, 123.1, 5.0, 7.3]), np.array([dh]))
        for i in range(4):
            npt.assert_almost_equal(finite_diff_3[i], grad_3[i], decimal=5)

        grad_4 = self.gp_gaussian.grad_log_likelihood(1.0, 0.0, np.array([14.0, 0.9]))
        dh = 0.0000001
        finite_diff_4 = FiniteDifferences.forward_difference(
            lambda params: self.gp_gaussian.log_likelihood(
                params[0], params[1], params[2:]
            ),
            np.array([1.0, 0.0, 14.0, 0.9]), np.array([dh]))
        for i in range(4):
            npt.assert_almost_equal(finite_diff_4[i], grad_4[i], decimal=5)

    def test_grad_log_likelihood_dict(self):
        grad = self.complex_gp_2.grad_log_likelihood_dict(
            1.82, 123.1, np.array([5.0, 1.0, -5.5, 10.0]))
        grad_2 = self.complex_gp_2.grad_log_likelihood(1.82, 123.1,
                                                       np.array([5.0, 1.0, -5.5, 10.0]))

        assert grad_2[0] == grad['var_noise']
        assert grad_2[1] == grad['mean']
        assert np.all(grad_2[2:] == grad['kernel_params'])

    def test_mle_parameters(self):
        # Results compared with the ones given by GPy

        np.random.seed(1)
        add = -45.946926660233636

        llh = self.gp_gaussian.log_likelihood(1.0, 0.0, np.array([100.0, 1.0]))
        npt.assert_almost_equal(llh + add, -59.8285565516, decimal=6)

        opt = self.gp_gaussian.mle_parameters(start=np.array([1.0, 0.0, 14.0, 0.9]))

        assert opt['optimal_value'] + add >= -67.1494227694

        compare = self.gp_gaussian.log_likelihood(9, 10.0, np.array([100.2, 1.1]))
        assert self.gp_gaussian_central.log_likelihood(9, 0.0, np.array([100.2, 1.1])) == compare

        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.5, n_points)
        points = np.linspace(0, 500, n_points)
        points = points.reshape([n_points, 1])
        kernel = Matern52.define_kernel_from_array(1, np.array([100.0, 1.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]

        evaluations = function + normal_noise

        training_data_gp = {
            "evaluations": list(evaluations),
            "points": points,
            "var_noise": []}

        gp_gaussian = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1])

        opt_3 = gp_gaussian.mle_parameters(random_seed=1314938)
        np.random.seed(1314938)
        start = gp_gaussian.sample_parameters_posterior(1)[0, :]
        opt_4 = gp_gaussian.mle_parameters(start)

        npt.assert_almost_equal(opt_3['optimal_value'], opt_4['optimal_value'])
        npt.assert_almost_equal(opt_3['solution'], opt_4['solution'], decimal=4)

    def test_objective_llh(self):
        funct = deepcopy(self.gp_gaussian.log_likelihood)

        def llh(a, b, c):
            return float(funct(a, b, c)) / 0.0

        self.gp_gaussian.log_likelihood = llh
        assert self.gp_gaussian.objective_llh(np.array([1.0, 3.0, 14.0, 0.9])) == -np.inf

    def test_sample_parameters_prior(self):
        sample = self.gp_gaussian.sample_parameters_prior(1, 1)[0]

        assert len(sample) == 4

        np.random.seed(1)

        lambda_ = np.abs(np.random.standard_cauchy(size=(1, 1)))
        a = np.abs(np.random.randn(1, 1) * lambda_ * np.var(self.training_data_gp['evaluations']))

        assert sample[0] == a[0][0]

        a = np.random.randn(1, 1) + np.mean(self.training_data_gp['evaluations'])
        assert sample[1] == a[0][0]

        n = self.training_data_gp['points'].shape[0]
        mean_ls = np.mean([abs(self.training_data_gp['points'][j, 0] -
                               self.training_data_gp['points'][h, 0]) for j in xrange(n) for h in
                           xrange(n)]) / 0.324
        a = SMALLEST_POSITIVE_NUMBER + np.random.rand(1, 1) * (mean_ls - SMALLEST_POSITIVE_NUMBER)
        assert sample[2] == a

        mean_var = np.var(self.training_data_gp['evaluations'])
        a = np.random.lognormal(mean=np.sqrt(mean_var), sigma=1.0, size=1) ** 2
        assert sample[3] == a[0]

    def test_log_prob_parameters(self):
        prob = self.gp_gaussian.log_prob_parameters(np.array([1.0, 3.0, 14.0, 0.9]))
        lp = self.gp_gaussian.log_likelihood(1.0, 3.0, np.array([14.0, 0.9])) - 10.13680717
        npt.assert_almost_equal(prob, lp)

    def test_set_samplers(self):
        type_kernel = [TASKS_KERNEL_NAME]
        training_data = {
            "evaluations": [42.2851784656, 72.3121248508],
            "points": [[0], [1]],
            "var_noise": []}
        dimensions = [2]

        gp_tk = GPFittingGaussian(type_kernel, training_data, dimensions)

        assert gp_tk.length_scale_indexes is None
        assert len(gp_tk.slice_samplers) == 1

        value = gp_tk.sample_parameters(1, random_seed=1)[-1]
        gp_tk_ = GPFittingGaussian(type_kernel, training_data, dimensions, n_burning=1,
                                   random_seed=1)
        assert np.all(gp_tk_.start_point_sampler == value)

        type_kernel = [PRODUCT_KERNELS_SEPARABLE, MATERN52_NAME, TASKS_KERNEL_NAME]
        training_data = {
            "evaluations": [42.2851784656, 72.3121248508],
            "points": [[0, 0], [1, 0]],
            "var_noise": []}
        dimensions = [2, 1, 1]
        gp = GPFittingGaussian(type_kernel, training_data, dimensions, n_burning=1, random_seed=1)

        gp2 = GPFittingGaussian(type_kernel, training_data, dimensions)
        value2 = gp2.sample_parameters(1, random_seed=1)[-1]
        assert np.all(gp.start_point_sampler == value2)

    def test_sample_parameters_posterior(self):
        start = self.gp.samples_parameters[-1]
        sample = self.gp.sample_parameters_posterior(1, 1)

        np.random.seed(1)
        sample2 = self.gp.sample_parameters_posterior(1, start_point=start)
        assert np.all(sample == sample2)
        assert sample.shape == (1, 4)

        start = self.gp.samples_parameters[-1]
        sample3 = self.gp.sample_parameters_posterior(2, 1)
        sample4 = self.gp.sample_parameters(2, random_seed=1, start_point=start)

        assert np.all(sample4[0] == sample3[0, :])
        assert np.all(sample4[1] == sample3[1, :])

    def test_fit_gp_regression(self):
        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.5, n_points)
        points = np.linspace(0, 500, n_points)
        points = points.reshape([n_points, 1])
        kernel = Matern52.define_kernel_from_array(1, np.array([100.0, 1.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]

        evaluations = function + normal_noise

        training_data_gp = {
            "evaluations": list(evaluations),
            "points": points,
            "var_noise": []}

        gp_gaussian = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1])
        gp_gaussian_2 = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1])

        new_gp = gp_gaussian.fit_gp_regression(random_seed=1314938)

        results = gp_gaussian_2.mle_parameters(random_seed=1314938)
        results = results['solution']

        npt.assert_almost_equal(new_gp.var_noise.value[0], results[0], decimal=6)
        npt.assert_almost_equal(new_gp.mean.value[0], results[1], decimal=6)
        npt.assert_almost_equal(new_gp.kernel_values, results[2:], decimal=1)

    def test_train(self):
        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.5, n_points)
        points = np.linspace(0, 500, n_points)
        points = points.reshape([n_points, 1])
        kernel = Matern52.define_kernel_from_array(1, np.array([100.0, 1.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]

        evaluations = function + normal_noise

        training_data_gp = {
            "evaluations": list(evaluations),
            "points": points,
            "var_noise": []}
        new_gp = GPFittingGaussian.train([MATERN52_NAME], [1], True, training_data_gp, None,
                                         random_seed=1314938)

        gp_gaussian = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1])
        gp_2 = gp_gaussian.fit_gp_regression(random_seed=1314938)

        npt.assert_almost_equal(new_gp.var_noise.value[0], gp_2.var_noise.value[0], decimal=6)
        npt.assert_almost_equal(new_gp.mean.value[0], gp_2.mean.value[0], decimal=6)
        npt.assert_almost_equal(new_gp.kernel_values, gp_2.kernel_values)

        gp_gaussian = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1])
        new_gp_2 = GPFittingGaussian.train([MATERN52_NAME], [1], False, training_data_gp, None)

        npt.assert_almost_equal(new_gp_2.var_noise.value[0], gp_gaussian.var_noise.value[0])
        npt.assert_almost_equal(new_gp_2.mean.value[0], gp_gaussian.mean.value[0], decimal=6)
        npt.assert_almost_equal(new_gp_2.kernel_values, gp_gaussian.kernel_values)

    def test_compute_posterior_parameters(self):
        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.5, n_points)
        points = np.linspace(0, 500, n_points)
        points = points.reshape([n_points, 1])
        kernel = Matern52.define_kernel_from_array(1, np.array([100.0, 1.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]
        evaluations = function + normal_noise

        training_data_gp = {
            "evaluations": list(evaluations[1:]),
            "points": points[1:, :],
            "var_noise": []}
        gp = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1], kernel_values=[100.0, 1.0],
                               mean_value=[0.0], var_noise_value=[0.5**2])

        new_point = np.array([points[0], points[1]])
        z = gp.compute_posterior_parameters(new_point)
        mean = z['mean']
        cov = z['cov']

        assert mean[1] - 2.0 * np.sqrt(cov[1, 1]) <= function[1]
        assert function[1] <= mean[1] + 2.0 * np.sqrt(cov[1, 1])
        assert mean[0] - 2.0 * np.sqrt(cov[0, 0]) <= function[0]
        assert function[0] <= mean[0] + 2.0 * np.sqrt(cov[0, 0])

        # Values obtained from GPy
        npt.assert_almost_equal(mean, np.array([0.30891226, 0.60256237]))
        npt.assert_almost_equal(cov, np.array([[0.48844879, 0.16799927], [0.16799927, 0.16536313]]))

    def test_sample_new_observations(self):
        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.5, n_points)
        points = np.linspace(0, 500, n_points)
        points = points.reshape([n_points, 1])
        kernel = Matern52.define_kernel_from_array(1, np.array([100.0, 1.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]
        evaluations = function + normal_noise

        training_data_gp = {
            "evaluations": list(evaluations[1:]),
            "points": points[1:, :],
            "var_noise": []}
        gp = GPFittingGaussian([MATERN52_NAME], training_data_gp, [1], kernel_values=[100.0, 1.0],
                               mean_value=[0.0], var_noise_value=[0.5**2])

        n_samples = 100
        samples = gp.sample_new_observations(np.array([[30.0]]), n_samples, random_seed=1)

        new_point = np.array([[30.0]])
        z = gp.compute_posterior_parameters(new_point)
        mean = z['mean']
        cov = z['cov']

        npt.assert_almost_equal(mean, np.mean(samples), decimal=1)
        npt.assert_almost_equal(cov, np.var(samples), decimal=1)

    def test_cross_validation_mle_parameters(self):
        type_kernel = [MATERN52_NAME]

        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.01, n_points)
        points = np.linspace(0, 100, n_points)
        points = points.reshape([n_points, 1])

        kernel = Matern52.define_kernel_from_array(1, np.array([100.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]
        evaluations = function + normal_noise

        training_data = {
            "evaluations": evaluations,
            "points": points,
            "var_noise": None}

        dimensions = [1]
        problem_name = 'a'

        result = \
            ValidationGPModel.cross_validation_mle_parameters(type_kernel, training_data,
                                                              dimensions, problem_name,
                                                              start=np.array([0.01**2, 0.0, 100.0]))

        compare = 'results/diagnostic_kernel/a/validation_kernel_histogram_a_' + MATERN52_NAME + \
                  '_same_correlation_False_10_None.png'
        assert result['filename_histogram'] == compare
        assert np.all(result['y_eval'] == evaluations)
        assert result['n_data'] == n_points
        assert result['filename_plot'] == 'results/diagnostic_kernel/a/' \
                                          'validation_kernel_mean_vs_observations_a_' + \
                                          MATERN52_NAME + '_same_correlation_False_10_None' + '.png'
        assert result['success_proportion'] >= 0.9

        noise = np.random.normal(0, 0.000001, n_points)
        evaluations_noisy = evaluations + noise

        training_data_2 = {
            "evaluations": evaluations_noisy,
            "points": points,
            "var_noise": np.array(n_points * [0.000001**2])}

        result_2 = \
            ValidationGPModel.cross_validation_mle_parameters(type_kernel, training_data_2,
                                                              dimensions, problem_name,
                                                              start=np.array([0.01**2, 0.0, 100.0]))

        compare = 'results/diagnostic_kernel/a/validation_kernel_histogram_a_' + MATERN52_NAME + \
                  '_same_correlation_False_10_None.png'
        assert result_2['filename_histogram'] == compare
        assert np.all(result_2['y_eval'] == evaluations_noisy)
        assert result_2['n_data'] == n_points

        compare = 'results/diagnostic_kernel/a/validation_kernel_mean_vs_observations_a_' + \
                  MATERN52_NAME + '_same_correlation_False_10_None.png'
        assert result_2['filename_plot'] == compare
        assert result_2['success_proportion'] >= 0.9

    def test_cross_validation_mle_parameters_2(self):
        type_kernel = [MATERN52_NAME]

        np.random.seed(5)
        n_points = 10
        normal_noise = np.random.normal(0, 0.01, n_points)
        points = np.linspace(0, 100, n_points)
        points = points.reshape([n_points, 1])

        kernel = Matern52.define_kernel_from_array(1, np.array([100.0]))
        function = SampleFunctions.sample_from_gp(points, kernel)
        function = function[0, :]
        evaluations = function + normal_noise

        training_data = {
            "evaluations": evaluations,
            "points": points,
            "var_noise": None}

        dimensions = [1]
        problem_name = 'a'

        result = \
            ValidationGPModel.cross_validation_mle_parameters(type_kernel, training_data,
                                                              dimensions, problem_name,
                                                              start=np.array([-1]))
        assert result['success_proportion'] == -1

    def test_check_value_within_ci(self):
        assert ValidationGPModel.check_value_within_ci(0, 1.0, 1.0)
        assert not ValidationGPModel.check_value_within_ci(3.1, 1.0, 1.0)
        assert not ValidationGPModel.check_value_within_ci(-1.1, 1.0, 1.0)
        assert ValidationGPModel.check_value_within_ci(0, 1.0, 1.0, var_noise=0.00001)

    def test_evaluate_cross_cov(self):

        value = self.complex_gp.evaluate_cross_cov(np.array([[2.0, 0.0]]), np.array([[1.0, 0.0]]),
                                           np.array([1.0, 0.0]))
        assert value == np.array([[0.52399410883182029]])

    def test_evaluate_grad_cross_cov_respect_point(self):
        value = self.gp.evaluate_grad_cross_cov_respect_point(np.array([[40.0]]),
                                                              np.array([[39.0], [38.0]]),
                                                              np.array([1.0, 1.0]))

        value_2 = ScaledKernel.evaluate_grad_respect_point(np.array([1.0, 1.0]),
                                                           np.array([[40.0]]),
                                                           np.array([[39.0], [38.0]]), 1,
                                                           *([MATERN52_NAME],))

        assert np.all(value == value_2)


        type_kernel = [MATERN52_NAME]
        training_data = {
            "evaluations":
                [42.2851784656, 72.3121248508, 1.0113231069, 30.9309246906, 15.5288331909],
            "points": [
                [42.2851784656], [72.3121248508], [1.0113231069], [30.9309246906], [15.5288331909]],
            "var_noise": []}
        dimensions = [1]

        gp = GPFittingGaussian(type_kernel, training_data, dimensions)
        value = gp.evaluate_grad_cross_cov_respect_point(np.array([[40.0]]),
                                                         np.array([[39.0], [38.0]]),
                                                         np.array([1.0]))

        value_2 = Matern52.evaluate_grad_respect_point(np.array([1.0]),
                                                       np.array([[40.0]]),
                                                       np.array([[39.0], [38.0]]), 1)

        assert np.all(value == value_2)

    def test_evaluate_hessian_respect_point(self):

        type_kernel = [MATERN52_NAME]
        training_data = {
            "evaluations":
                [42.2851784656, 72.3121248508, 1.0113231069, 30.9309246906, 15.5288331909],
            "points": [
                [42.2851784656], [72.3121248508], [1.0113231069], [30.9309246906], [15.5288331909]],
            "var_noise": []}
        dimensions = [1]

        gp = GPFittingGaussian(type_kernel, training_data, dimensions)
        value = gp.evaluate_hessian_cross_cov_respect_point(np.array([[40.0]]),
                                                         np.array([[39.0], [38.0]]),
                                                         np.array([1.0]))

        value_2 = Matern52.evaluate_hessian_respect_point(np.array([1.0]),
                                                       np.array([[40.0]]),
                                                       np.array([[39.0], [38.0]]), 1)
        assert np.all(value == value_2)


    def test_get_historical_best_solution(self):
        max_ = self.gp.get_historical_best_solution()
        assert max_ == 72.3121248508

        max_ = self.gp_3.get_historical_best_solution(noisy_evaluations=True)

        assert max_ == self.gp_3.compute_posterior_parameters(
                np.array([[72.3121248508]]), only_mean=True)['mean']

    def test_gradient_posterior_parameters(self):
        point = np.array([[49.5]])
        grad = self.gp_gaussian.gradient_posterior_parameters(point)

        dh = 0.0000001
        finite_diff = FiniteDifferences.forward_difference(
            lambda x: self.gp_gaussian.compute_posterior_parameters(
                x.reshape((1, len(x))), only_mean=True)['mean'],
            np.array([49.5]), np.array([dh]))

        npt.assert_almost_equal(grad['mean'], finite_diff[0])

        dh = 0.0000001
        finite_diff = FiniteDifferences.forward_difference(
            lambda x: self.gp_gaussian.compute_posterior_parameters(
                x.reshape((1, len(x))))['cov'],
            np.array([49.5]), np.array([dh]))

        npt.assert_almost_equal(grad['cov'], finite_diff[0])

