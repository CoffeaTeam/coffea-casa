import dask
import pytest
import coffea_casa.config


def test_dask_config():
    assert dask.config.get('jobqueue.coffea-casa.worker-image') == "hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu:development"
