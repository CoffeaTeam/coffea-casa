import dask
import pytest
import coffea_casa.config

import os    
os.environ['TAG'] = '2021.07.22'


def test_dask_config():
    assert dask.config.get('jobqueue.coffea-casa.worker-image') == "coffeateam/coffea-casa-analysis:2021.07.13"