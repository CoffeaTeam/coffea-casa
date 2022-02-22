"""conftest.py has a special meaning to pytest

ref: https://docs.pytest.org/en/latest/writing_plugins.html#conftest-py-plugins

File is taken from: https://github.com/jupyterhub/zero-to-jupyterhub-k8s/blob/main/tests/conftest.py
"""

import os
import requests
import textwrap
import uuid

from urllib.parse import urlparse

import pytest
import yaml


def pytest_configure(config):
    """
    A pytest hook, see:
    https://docs.pytest.org/en/2.7.3/plugins.html#_pytest.hookspec.pytest_configure
    """
    # Ignore InsecureRequestWarning associated with https:// web requests
    config.addinivalue_line("filterwarnings", "ignore:Unverified HTTPS request")
    # register our custom markers
    config.addinivalue_line(
        "markers", "netpol: mark test that require network policy enforcement"
    )


@pytest.fixture(scope="module")
def admin_api_token():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(base_dir, "charts/coffea-casa/values.yaml")) as f:
        y = yaml.safe_load(f)
    token = y["jupyterhub"]["hub"]["services"]["test"]["apiToken"]
    return token


@pytest.fixture(scope="module")
def request_data(admin_api_token):
    hub_url = os.environ.get("HUB_URL", "https://local.jovyan.org:30443")
    return {
        "token": admin_api_token,
        "hub_url": f'{hub_url.rstrip("/")}/hub/api',
        "headers": {"Authorization": f"token {admin_api_token}"},
        "test_timeout": 60,
        "request_timeout": 25,
    }


@pytest.fixture(scope="module")
def pebble_acme_ca_cert():
    """
    Acquires Pebble's ephemeral root certificate that when trusted implies trust
    to the ACME client's certificates. We can use the response of this function
    when we make web requests with the requests library.

        requests.get(..., verify=<True|False|path_to_certificate>)

    If HUB_URL is http:// return False since no certificate is required
    """
    if os.getenv("HUB_URL", "").startswith("http://"):
        return False

    # 'localhost' may resolve to an ipv6 address which may not be supported on older K3S
    # 127.0.0.1 is more reliable
    response = requests.get("https://127.0.0.1:32444/roots/0", verify=False, timeout=10)
    if not response.ok:
        return True

    base_dir = os.path.dirname(os.path.dirname(__file__))
    cert_path = os.path.join(base_dir, "ephemeral-pebble-acme-ca.crt")
    with open(cert_path, "w+") as f:
        f.write(response.text)
    return cert_path


class JupyterRequest:
    def __init__(self, request_data, pebble_acme_ca_cert):
        self.request_data = request_data
        self.pebble_acme_ca_cert = pebble_acme_ca_cert

    def _setup_kwargs(self, kwargs):
        kwargs["headers"] = kwargs.get("headers", self.request_data["headers"])
        kwargs["timeout"] = kwargs.get("timeout", self.request_data["request_timeout"])

    def delete(self, api, **kwargs):
        self._setup_kwargs(kwargs)
        return requests.delete(
            self.request_data["hub_url"] + api,
            verify=self.pebble_acme_ca_cert,
            **kwargs,
        )

    def get(self, api, **kwargs):
        self._setup_kwargs(kwargs)
        return requests.get(
            self.request_data["hub_url"] + api,
            verify=self.pebble_acme_ca_cert,
            **kwargs,
        )

    def post(self, api, **kwargs):
        self._setup_kwargs(kwargs)
        return requests.post(
            self.request_data["hub_url"] + api,
            verify=self.pebble_acme_ca_cert,
            **kwargs,
        )

    def put(self, api, **kwargs):
        self._setup_kwargs(kwargs)
        return requests.put(
            self.request_data["hub_url"] + api,
            verify=self.pebble_acme_ca_cert,
            **kwargs,
        )


@pytest.fixture(scope="function")
def api_request(request_data, pebble_acme_ca_cert):
    return JupyterRequest(request_data, pebble_acme_ca_cert)


@pytest.fixture(scope="function")
def jupyter_user(api_request):
    """
    A temporary unique JupyterHub user
    """
    username = "testuser-" + str(uuid.uuid4())
    r = api_request.post("/users/" + username)
    assert r.status_code == 201
    yield username
    r = api_request.delete("/users/" + username)
    assert r.status_code == 204

