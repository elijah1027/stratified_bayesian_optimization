from __future__ import absolute_import

from os import path
import os

import numpy as np

from stratified_bayesian_optimization.initializers.log import SBOLog
from stratified_bayesian_optimization.entities.domain import DomainEntity
from stratified_bayesian_optimization.entities.domain import BoundsEntity
from stratified_bayesian_optimization.lib.constant import (
    DOMAIN_DIR,
    PROBLEM_DIR,
)
from stratified_bayesian_optimization.util.json_file import JSONFile

logger = SBOLog(__name__)


class DomainService(object):
    _disc_x_filename = 'discretization_domain_x_bounds_{bounds}_number_points_' \
                       '{number_points_each_dimension}.json'.format

    @classmethod
    def load_discretization(cls, problem_name, bounds_domain_x, number_points_each_dimension_x):
        """
        Try to load discretization for problem_name from file. If the file doesn't exist, will
        generate the discretization and store it.

        :param problem_name: (str)
        :param bounds_domain_x: ([BoundsEntity])
        :param number_points_each_dimension_x: ([int])

        :return: [[float]]
        """

        bounds_str = BoundsEntity.get_bounds_as_lists(bounds_domain_x)

        filename = cls._disc_x_filename(
            name=problem_name,
            bounds=bounds_str,
            number_points_each_dimension=number_points_each_dimension_x
        )

        domain_dir = path.join(PROBLEM_DIR, problem_name, DOMAIN_DIR)

        if not os.path.exists(domain_dir):
            os.mkdir(domain_dir)

        domain_path = path.join(domain_dir, filename)

        discretization_data = JSONFile.read(domain_path)
        if discretization_data is not None:
            return discretization_data

        logger.info('Gnerating discretization of domain_x')
        discretization_data = DomainEntity.discretize_domain(bounds_domain_x,
                                                             number_points_each_dimension_x)
        logger.info('Generated discretization of domain_x')

        JSONFile.write(discretization_data, domain_path)

        return discretization_data

    @classmethod
    def from_dict(cls, spec):
        """
        Create from dict

        :param spec: dict
        :return: DomainEntity
        """
        entry = {}
        entry['dim_x'] = int(spec['dim_x'])
        entry['choose_noise'] = spec['choose_noise']
        entry['bounds_domain_x'] = spec['bounds_domain_x']

        entry['dim_w'] = spec.get('dim_w')
        entry['bounds_domain_w'] = spec.get('bounds_domain_w')
        entry['domain_w'] = spec.get('domain_w')

        if 'number_points_each_dimension' in spec:
            entry['discretization_domain_x'] = \
                cls.load_discretization(spec['problem_name'], entry['bounds_domain_x'],
                                        spec['number_points_each_dimension'])

        return DomainEntity(entry)

    @classmethod
    def get_points_domain(cls, n_samples, bounds_domain, type_bounds=None, random_seed=None):
        """
        Returns a list with points in the domain
        :param n_samples: int
        :param bounds_domain: [([float, float] or [float])], the first case is when the bounds are
            lower or upper bound of the respective entry; in the second case, it's list of finite
            points representing the domain of that entry.
        :param type_bounds: [0 or 1], 0 if the bounds are lower or upper bound of the respective
            entry, 1 if the bounds are all the finite options for that entry.
        :param random_seed: int
        :return: [[float]]
        """
        if random_seed is not None:
            np.random.seed(random_seed)

        if type_bounds is None:
            type_bounds = []
            type_bounds += [0] * len(bounds_domain)

        points = []

        for j in xrange(len(bounds_domain)):
            entry = cls.get_point_one_dimension_domain(n_samples, bounds_domain[j],
                                                       type_bounds=type_bounds[j])
            points.append(entry)

        return [[point[j] for point in points] for j in xrange(n_samples)]

    @classmethod
    def get_point_one_dimension_domain(cls, n_samples, bounds, type_bounds=0):
        """
        Returns n random points in only one dimension

        :param n_samples: int
        :param bounds: [float, float] or [float]; in the first case, those are the bounds; and in
            the second case, those are the finite points that represent the domain.
        :param type_bounds: 0 or 1,  0 if the bounds are lower or upper bound of the respective
            entry, 1 if the bounds are all the finite options for the entry.
        :return: [float]
        """
        if type_bounds == 0:
            return list(np.random.uniform(bounds[0], bounds[1], n_samples))
        else:
            return list(np.random.choice(bounds, n_samples))