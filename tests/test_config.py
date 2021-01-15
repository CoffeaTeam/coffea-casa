import dask
import pytest
import coffea_casa.config


def test_dask_config():
    assert dask.config.get('jobqueue.coffea-casa.worker-image') == "coffeateam/coffea-casa-analysis:0.3.11"
