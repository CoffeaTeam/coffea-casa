"""
These tests commonl use JupyterHub's REST API:
http://petstore.swagger.io/?url=https://raw.githubusercontent.com/jupyterhub/jupyterhub/HEAD/docs/rest-api.yml
"""

import os
import re
import subprocess
import time

import pytest
import requests
import yaml


def test_api_root(api_request):
    """
    Tests the hub api's root endpoint (/). The hub's version should be returned.
    A typical jupyterhub logging response to this test:
        [I 2019-09-25 12:03:12.051 JupyterHub log:174] 200 GET /hub/api (test@127.0.0.1) 9.57ms
    """

    # load app version of chart
    here = os.path.dirname(os.path.abspath(__file__))
    chart_yaml = os.path.join(here, os.pardir, "charts", "coffea-casa", "Chart.yaml")

    with open(chart_yaml) as f:
        chart = yaml.safe_load(f)
        jupyterhub_version = chart["appVersion"]

    print("asking for the hub's version")
    r = api_request.get("")
    assert r.status_code == 200
    assert r.json().get("version", "version-missing") == jupyterhub_version


    