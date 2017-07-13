from __future__ import absolute_import

import numpy as np

from os import path
import os

from stratified_bayesian_optimization.initializers.log import SBOLog
from stratified_bayesian_optimization.lib.constant import (
    UNIFORM_FINITE,
    TASKS,
    QUADRATURES,
    POSTERIOR_MEAN,
    TASKS_KERNEL_NAME,
    LBFGS_NAME,
    DEBUGGING_DIR,
)
from stratified_bayesian_optimization.lib.la_functions import (
    cho_solve,
)
from stratified_bayesian_optimization.services.domain import (
    DomainService,
)
from stratified_bayesian_optimization.lib.expectations import (
    uniform_finite,
    gradient_uniform_finite,
)
from stratified_bayesian_optimization.lib.optimization import Optimization
from stratified_bayesian_optimization.util.json_file import JSONFile

logger = SBOLog(__name__)


class BayesianQuadrature(object):
    _filename = 'opt_post_mean_gp_{model_type}_{problem_name}_{type_kernel}_{training_name}.json'.\
        format

    _expectations_map = {
        UNIFORM_FINITE: {
            'expectation': uniform_finite,
            'grad_expectation': gradient_uniform_finite,
            'parameter': TASKS,
        },
    }

    def __init__(self, gp_model, x_domain, distribution, parameters_distribution=None):
        """

        :param gp_model: gp_fitting_gaussian instance
        :param x_domain: [int], indices of the x domain
        :param distribution: (str), it must be in the list of distributions:
            [UNIFORM_FINITE]
        :param parameters_distribution: (dict) dictionary with parameters of the distribution.
            -UNIFORM_FINITE: dict{TASKS: int}
        """
        self.gp = gp_model

        if parameters_distribution == {}:
            parameters_distribution = None

        if parameters_distribution is None and distribution == UNIFORM_FINITE:
            for name in self.gp.kernel.names:
                if name == TASKS_KERNEL_NAME:
                    n = self.gp.kernel.kernels[name].n_tasks
                    break
            parameters_distribution = {TASKS: n}

        self.parameters_distribution = parameters_distribution
        self.dimension_domain = self.gp.dimension_domain
        self.x_domain = x_domain
        self.w_domain = [i for i in range(self.gp.dimension_domain) if i not in x_domain]
        self.expectation = self._expectations_map[distribution]
        self.arguments_expectation = {}

        if self.expectation['parameter'] == TASKS:
            n_tasks = self.parameters_distribution.get(TASKS)
            self.arguments_expectation['domain_random'] = np.arange(n_tasks).reshape((n_tasks, 1))

        self.cache_quadratures = {}
        self.cache_posterior_mean = {}
        self.optimal_solutions = [] # The optimal solutions are written here

    def _get_cached_data(self, index, name):
        """
        :param index: tuple. (parameters_kernel, )
        :param name: (str) QUADRATURES or POSTERIOR_MEAN

        :return: cached data if it's cached, otherwise False
        """

        if name == QUADRATURES:
            if index in self.cache_quadratures:
                return self.cache_quadratures[index]
        if name == POSTERIOR_MEAN:
            if index in self.cache_posterior_mean:
                return self.cache_posterior_mean[index]
        return None

    def _updated_cached_data(self, index, value, name):
        """

        :param index: tuple. (parameters_kernel, )
        :param value: value to be cached
        :param name: (str) QUADRATURES or POSTERIOR_MEAN

        """

        if name == QUADRATURES:
            self.cache_quadratures = {}
            self.cache_quadratures[index] = value
        if name == POSTERIOR_MEAN:
            self.cache_posterior_mean = {}
            self.cache_posterior_mean[index] = value

    def evaluate_quadrate_cov(self, point, parameters_kernel):
        """
        Evaluate the quadrature cov, i.e.
            Expectation(cov((point,w_i), (point,w'_j))) respect to w_i, w_j.

        :param point: np.array(1xk)
        :param parameters_kernel: np.array(l)
        :return: np.array(m)
        """
        f = lambda x: self.gp.evaluate_cov(x, parameters_kernel)

        parameters = {
            'f': f,
            'point': point,
            'index_points': self.x_domain,
            'index_random': self.w_domain,
            'double': True,
        }

        parameters.update(self.arguments_expectation)

        return self.expectation['expectation'](**parameters)

    def evaluate_quadrature_cross_cov(self, point, points_2, parameters_kernel):
        """
        Evaluate the quadrature cross cov respect to point, i.e.
            Expectation(cov((x_i,w_i), (x'_j,w'_j))) respect to w_i, where point = (x_i), and
            points_2 = (x'_j, w'_j).
        This is [B(x, j)] in the SBO paper.

        :param point: np.array(txk)
        :param points_2: np.array(mxk')
        :param parameters_kernel: np.array(l)
        :return: np.array(txm)
        """

        f = lambda x: self.gp.evaluate_cross_cov(x, points_2, parameters_kernel)

        parameters = {
            'f': f,
            'point': point,
            'index_points': self.x_domain,
            'index_random': self.w_domain,
        }

        parameters.update(self.arguments_expectation)

        B = self.expectation['expectation'](**parameters)

        return B

    def evaluate_grad_quadrature_cross_cov(self, point, points_2, parameters_kernel):
        """
        Evaluate the gradient respect to the point of the quadrature cross cov i.e.
            gradient(Expectation(cov((x_i,w_i), (x'_j,w'_j)))), where point = (x_i), and
            points_2 = (x'_j, w'_j).
        This is gradient[B(x, j)] in the SBO paper.

        :param point: np.array(1xk)
        :param points_2: np.array(mxk')
        :param parameters_kernel: np.array(l)
        :return: np.array(kxm)
        """

        parameters = {
            'f': self.gp.evaluate_grad_cross_cov_respect_point,
            'point': point,
            'points_2': points_2,
            'index_points': self.x_domain,
            'index_random': self.w_domain,
            'parameters_kernel': parameters_kernel,
        }

        parameters.update(self.arguments_expectation)

        gradient = self.expectation['grad_expectation'](**parameters)

        return gradient

    def compute_posterior_parameters(self, points, var_noise=None, mean=None,
                                     parameters_kernel=None, historical_points=None,
                                     historical_evaluations=None, only_mean=False, cache=True):
        """
        Compute posterior mean and covariance of the GP on G(x) = E[F(x, w)].

        :param points: np.array(txk) Only if only_mean is True!
        :param var_noise: float
        :param mean: float
        :param parameters_kernel: np.array(l)
        :param historical_points: np.array(nxm)
        :param historical_evaluations: np.array(n)
        :param cache: (boolean) get cached data only if cache is True
        :param only_mean: (boolean) computes only the mean if it's True.

        :return: {
            'mean': np.array(t),
            'cov': float,
        }
        """

        if var_noise is None:
            var_noise = self.gp.var_noise.value[0]

        if parameters_kernel is None:
            parameters_kernel = self.gp.kernel.hypers_values_as_array

        if mean is None:
            mean = self.gp.mean.value[0]

        if historical_points is None:
            historical_points = self.gp.data['points']

        if historical_evaluations is None:
            historical_evaluations = self.gp.data['evaluations']

        chol_solve = self.gp._cholesky_solve_vectors_for_posterior(
            var_noise, mean, parameters_kernel, historical_points=historical_points,
            historical_evaluations=historical_evaluations, cache=cache)

        solve = chol_solve['solve']
        chol = chol_solve['chol']

        n = points.shape[0]
        m = historical_points.shape[0]

        vec_covs = np.zeros((n, m))
        for i in xrange(n):
            vec_covs[i, :] = self.evaluate_quadrature_cross_cov(
                points[i:i+1,:], historical_points, parameters_kernel)

        mu_n = mean + np.dot(vec_covs, solve)

        if only_mean:
            return {
            'mean': mu_n,
            'cov': None,
        }

        solve_2 = cho_solve(chol, vec_covs.transpose())

        cov_n = self.evaluate_quadrate_cov(points, parameters_kernel) - np.dot(vec_covs, solve_2)

        return {
            'mean': mu_n,
            'cov': cov_n,
        }

    def gradient_posterior_mean(self, point, var_noise=None, mean=None, parameters_kernel=None,
                                historical_points=None, historical_evaluations=None, cache=True):
        """
        Compute posterior mean and covariance of the GP on G(x) = E[F(x, w)].

        :param point: np.array(1xk)
        :param var_noise: float
        :param mean: float
        :param parameters_kernel: np.array(l)
        :param historical_points: np.array(nxm)
        :param historical_evaluations: np.array(n)
        :param cache: (boolean) get cached data only if cache is True

        :return: np.array(k)
        """

        if var_noise is None:
            var_noise = self.gp.var_noise.value[0]

        if parameters_kernel is None:
            parameters_kernel = self.gp.kernel.hypers_values_as_array

        if mean is None:
            mean = self.gp.mean.value[0]

        if historical_points is None:
            historical_points = self.gp.data['points']

        if historical_evaluations is None:
            historical_evaluations = self.gp.data['evaluations']

        gradient = self.evaluate_grad_quadrature_cross_cov(point, historical_points,
                                                           parameters_kernel)

        chol_solve = self.gp._cholesky_solve_vectors_for_posterior(
            var_noise, mean, parameters_kernel, historical_points=historical_points,
            historical_evaluations=historical_evaluations, cache=cache)

        solve = chol_solve['solve']

        return np.dot(gradient, solve)

    def objective_posterior_mean(self, point):
        """
        Computes the posterior mean evaluated on point.

        :param point: np.array(k)
        :return: float
        """

        point = point.reshape((1, len(point)))

        return self.compute_posterior_parameters(point, only_mean=True)['mean']

    def grad_posterior_mean(self, point):
        """
        Computes the gradient of the posterior mean evaluated on point.

        :param point: np.array(k)
        :return: np.array(k)
        """

        point = point.reshape((1, len(point)))
        return self.gradient_posterior_mean(point)

    def optimize_posterior_mean(self, start=None, random_seed=None, minimize=False):
        if random_seed is not None:
            np.random.seed(random_seed)

        bounds_x = [self.gp.bounds[i] for i in xrange(len(self.gp.bounds)) if i in
                    self.x_domain]

        if start is None:
            if len(self.optimal_solutions) > 0:
                start = self.optimal_solutions[-1]['solution']
            else:
                start = DomainService.get_points_domain(1, bounds_x,
                                                        type_bounds=len(self.x_domain)*[0])
                start = np.array(start[0])

        bounds = [tuple(bound) for bound in bounds_x]

        objective_function = self.objective_posterior_mean
        grad_function = self.grad_posterior_mean

        optimization = Optimization(
            LBFGS_NAME,
            objective_function,
            bounds,
            grad_function,
            minimize=minimize)

        results = optimization.optimize(start)

        logger.info("Results of the optimization of the posterior mean: ")
        logger.info(results)

        self.optimal_solutions.append(results)

        return results

    def compute_posterior_parameters_kg(self, points, candidate_point, var_noise=None, mean=None,
                                        parameters_kernel=None):
        """
        Compute posterior parameters of the GP after integrating out the random parameters needed
        to compute the knowledge gradient (vectors "a" and "b" in the SBO paper).

        :param points: np.array(nxk)
        :param candidate_point: np.array(1xm), (new_x, new_w)
        :param var_noise: float
        :param mean: float
        :param parameters_kernel: np.array(l)

        :return: {
            'mean': np.array(n),
            'cov': np.array(nxn)
        }
        """

        if var_noise is None:
            var_noise = self.gp.var_noise.value[0]

        if parameters_kernel is None:
            parameters_kernel = self.gp.kernel.hypers_values_as_array

        if mean is None:
            mean = self.gp.mean.value[0]

        chol_solve = self.gp._cholesky_solve_vectors_for_posterior(
            var_noise, mean, parameters_kernel)
        chol = chol_solve['chol']
        solve = chol_solve['solve']

        n = points.shape[0]
        m = self.gp.data['points'].shape[0]

        b_new = np.zeros((n, 1))

        compute_vec_covs = False
        vec_covs = self._get_cached_data((tuple(parameters_kernel, )), QUADRATURES)

        if vec_covs is None:
            compute_vec_covs = True
            vec_covs = np.zeros((n, m))

        for i in xrange(n):
            if compute_vec_covs:
                vec_covs[i, :] = self.evaluate_quadrature_cross_cov(
                    points[i:i+1,:], self.gp.data['points'], parameters_kernel)
            b_new[i, 0] = self.evaluate_quadrature_cross_cov(
                points[i:i+1,:], candidate_point, parameters_kernel)

        if compute_vec_covs:
            self._updated_cached_data((tuple(parameters_kernel), ), vec_covs, QUADRATURES)

        mu_n = self._get_cached_data((tuple(parameters_kernel),), POSTERIOR_MEAN)

        if mu_n is None:
            mu_n = mean + np.dot(vec_covs, solve)
            self._updated_cached_data((tuple(parameters_kernel),), mu_n, POSTERIOR_MEAN)

        # TODO: CACHE SO WE DON'T COMPUTE MU_N ALL THE TIME
        cross_cov = self.gp.evaluate_cross_cov(candidate_point, self.gp.data['points'],
                                                parameters_kernel)

        solve_2 = cho_solve(chol, cross_cov[0, :])
        numerator = b_new[:, 0] - np.dot(vec_covs, solve_2)

        new_cross_cov = self.gp.evaluate_cross_cov(candidate_point, candidate_point,
                                                   parameters_kernel)

        denominator = new_cross_cov - np.dot(cross_cov, solve_2)
        denominator = denominator[0, 0]

        return {
            'a': mu_n,
            'b': (numerator ** 2) / denominator,
        }

    def sample_new_observations(self, point, n_samples, random_seed=None):
        """
        Sample g(point) = E[f(point,w)] n_samples times.

        :param point: np.array(1xn)
        :param n_samples: int
        :param random_seed: int
        :return: np.array(n_samples)
        """

        if random_seed is not None:
            np.random.seed(random_seed)

        posterior_parameters = self.compute_posterior_parameters(point)
        mean = posterior_parameters['mean']
        var = posterior_parameters['cov']

        samples = np.random.normal(mean, np.sqrt(var), n_samples)

        return samples

    def write_debug_data(self, problem_name, model_type, training_name):
        """
        Write information about the different optimizations realized.

        :param problem_name: (str)
        :param model_type: (str)
        :param training_name: (str)
        """

        if not os.path.exists(DEBUGGING_DIR):
            os.mkdir(DEBUGGING_DIR)

        debug_dir = path.join(DEBUGGING_DIR, problem_name)

        if not os.path.exists(debug_dir):
            os.mkdir(debug_dir)

        kernel_name = ''
        for kernel in self.gp.type_kernel:
            kernel_name += kernel + '_'
        kernel_name = kernel_name[0: -1]

        f_name = self._filename(model_type=model_type,
                                problem_name=problem_name,
                                type_kernel=kernel_name,
                                training_name=training_name)

        debug_path = path.join(debug_dir, f_name)

        JSONFile.write(self.optimal_solutions, debug_path)