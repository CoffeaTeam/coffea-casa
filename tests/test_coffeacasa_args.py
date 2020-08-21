import pytest
import os
from pathlib import Path
from coffea_casa import CoffeaCasaCluster
from distributed.security import Security

# Security settings for coffea-casa Dask scheduler
SECRETS_DIR = Path('/etc/cmsaf-secrets')
CA_FILE = SECRETS_DIR / "ca.pem"
CERT_FILE = SECRETS_DIR / "hostcert.pem"

@pytest.fixture
def default_modified_kwargs():
    return CoffeaCasaCluster._modify_job_kwargs({})


def test_default_dask_container_port(default_modified_kwargs):
    assert default_modified_kwargs["job_extra"]["dask_container_port"] == 8787


def test_can_override_dask_container_port():
    kwargs = CoffeaCasaCluster._modify_job_kwargs(dict(job_extra={"dask_container_port": 8788}))
    assert kwargs["job_extra"]["dask_container_port"] == 8788


def test_default_protocol(default_modified_kwargs):
    if CA_FILE.is_file() and CERT_FILE.is_file():
        assert default_modified_kwargs["scheduler_options"]["protocol"] == 'tls'
    else:
        assert default_modified_kwargs["scheduler_options"]["protocol"] == 'tcp'


@pytest.mark.skip(reason="TLS is still not working out-of-the-box")
def test_args_security():
    dirname = os.path.dirname(__file__)
    key = os.path.join(dirname, "key.pem")
    cert = os.path.join(dirname, "ca.pem")
    security = Security(
        tls_ca_file=cert,
        tls_scheduler_key=key,
        tls_scheduler_cert=cert,
        tls_worker_key=key,
        tls_worker_cert=cert,
        tls_client_key=key,
        tls_client_cert=cert,
        require_encryption=True)
    with CoffeaCasaCluster(cores=1,
                           memory="100MB",
                           disk="100MB",
                           worker_image="coffeateam/coffea-casa:0.2.5",
                           security=security
                           ) as cluster:
        kwargs = cluster._modify_job_kwargs({})
        assert security.get_connection_args("scheduler").get("require_encryption") is True
        assert kwargs["security"] == security
        assert kwargs["scheduler_options"]["protocol"] == 'tls'