from __future__ import absolute_import



import numpy as np

from stratified_bayesian_optimization.initializers.log import SBOLog

logger = SBOLog(__name__)


def SGD(start, gradient, n, args=(), kwargs={}, bounds=None, learning_rate=0.1, momentum=0.5,
        maxepoch=250):
    """
    SGD to minimize sum(i=0 -> n) (1/n) * f(x). Batch sizes are of size 1.
    :param start: np.array(n)
    :param gradient:
    :param n:
    :param learning_rate:
    :param momentum:
    :param maxepoch:
    :param args: () arguments for the gradient
    :param kwargs:
    :param bounds: [(min, max)] for each point
    :return: np.array(n)
    """

    project = False
    if bounds is not None:
        project = True

    point = start
    v = np.zeros(len(start))
    times_out_boundary = 0

    for iteration in xrange(maxepoch):
        previous = point.copy()
        for j in xrange(n):
            gradient_ = gradient(point, *args, **kwargs)

            if gradient_ is np.nan:
                norm_point = np.sqrt(np.sum(point ** 2))
                perturbation = norm_point * 1e-6

                if project:
                    parameters_uniform = []
                    for i in range(len(bounds)):
                        bound = bounds[i]
                        dist = point[i] - bound[0]
                        lb = min(perturbation, dist)
                        dist = bound[1] - point[i]
                        ub = min(perturbation, dist)
                        parameters_uniform.append([-lb, ub])
                else:
                    parameters_uniform = len(point) * [[-perturbation, perturbation]]

                perturbation = []
                for i in range(len(point)):
                    lb = parameters_uniform[i][0]
                    ub = parameters_uniform[i][1]
                    perturbation.append(np.random.uniform(lb, ub))
                perturbation = np.array(perturbation)
                point = point + perturbation
                gradient_ = gradient(point, *args, **kwargs)

            v = momentum * v + gradient_
            point -= learning_rate * v

            in_domain = True
            if project:
                for dim, bound in enumerate(bounds):
                    if point[dim] < bound[0] or point[dim] > bound[1]:
                        in_domain = False
                        break

            if project and not in_domain:
                for dim, bound in enumerate(bounds):
                    if bound[0] is not None:
                        point[dim] = max(bound[0], point[dim])
                    if bound[1] is not None:
                        point[dim] = min(bound[1], point[dim])
                    v = np.zeros(len(start))
                    times_out_boundary += 1

                    if times_out_boundary > 1:
                        momentum = 0
                        learning_rate *= 0.5
                        v = np.zeros(len(start))

        den_norm = (np.sqrt(np.sum(previous ** 2)))

        if den_norm == 0:
            norm = np.sqrt(np.sum((previous - point) ** 2)) / 1e-2
        else:
            norm = np.sqrt(np.sum((previous - point) ** 2)) / den_norm
        if norm < 0.01:
            break

    return point
