# -*- coding: utf-8 -*-
from __future__ import absolute_import

import dask
import yaml
import os
from .coffea_casa import CoffeaCasaCluster
from .coffea_casa_method import coffea_casa_cluster
from . import config

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions


def is_number(in_value):
    try:
        float(in_value)
        return True
    except ValueError:
        return False
