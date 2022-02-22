import os
from urllib.parse import urlparse
import pytest
import yaml

# From jupyterhub/zero-to-jupyterhub-k8s/509fc47a496a9988b2c4a4114cd101f699114298/tests/conftest.py
@pytest.fixture(scope="module")
def test_admin_api_token():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "values.yaml")) as f:
        y = yaml.safe_load(f)
    token = y["hub"]["services"]["test"]["apiToken"]
    return token

# From jupyterhub/zero-to-jupyterhub-k8s/509fc47a496a9988b2c4a4114cd101f699114298/tests/conftest.py
@pytest.fixture(scope="module")
def test_request_data(test_admin_api_token):
    hub_url = os.environ.get("HUB_URL", "https://local.jovyan.org:30443")
    return {
        "token": test_admin_api_token,
        "hub_url": f'{hub_url.rstrip("/")}/hub/api',
        "headers": {"Authorization": f"token {test_admin_api_token}"},
        "test_timeout": 60,
        "request_timeout": 25,
    }