"""
# coffea-casa/config.py
# https://docs.dask.org/en/latest/configuration.html
"""
import os
import yaml

import dask.config

fn = os.path.join(os.path.dirname(__file__), "jobqueue-coffea-casa.yaml")

with open(fn) as f:
    defaults = yaml.safe_load(f)
dask.config.update_defaults(defaults)

dask.config.ensure_file(source=fn, comment=True)
