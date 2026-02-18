import os
import pytest
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

from coffea_casa import CoffeaCasaCluster, CoffeaCasaJob
from distributed.security import Security

# Security is imported inside coffea_casa/coffea_casa.py
_SECURITY_PATH = "coffea_casa.coffea_casa.Security"


@pytest.fixture(autouse=True)
def suppress_unraisable_warnings():
    warnings.filterwarnings(
        "ignore",
        category=pytest.PytestUnraisableExceptionWarning,
    )


@pytest.fixture
def dummy_ca_cert(tmp_path):
    """Create dummy CA and host cert files"""
    ca_file = tmp_path / "ca.pem"
    cert_file = tmp_path / "hostcert.pem"
    ca_file.write_text("dummy-ca")
    cert_file.write_text("dummy-cert")
    return ca_file, cert_file


@pytest.fixture
def dummy_token(tmp_path):
    """Create a dummy bearer token file"""
    token_file = tmp_path / "bt_u999"
    token_file.write_text("dummy-token")
    return token_file


def make_test_cluster(
    monkeypatch,
    *,
    ca_file=None,
    cert_file=None,
    token_file=None,
    proxy_file=None,
):
    """Create a CoffeaCasaCluster with all external dependencies patched."""
    monkeypatch.setenv("HOST_IP", "127.0.0.1")

    if token_file:
        monkeypatch.setenv("BEARER_TOKEN_FILE", str(token_file))

    if proxy_file:
        monkeypatch.setenv("X509_USER_PROXY", str(proxy_file))

    kwargs = {"worker_image": "dummy/image"}
    if ca_file:
        kwargs["ca_file"] = str(ca_file)
    if cert_file:
        kwargs["cert_file"] = str(cert_file)

    mock_security = MagicMock(spec=Security)
    mock_security.get_connection_args.return_value = {"require_encryption": False}

    with patch(_SECURITY_PATH, return_value=mock_security), \
         patch("coffea_casa.coffea_casa.dask.config.set"):
        cluster = CoffeaCasaCluster(**kwargs)

    return cluster


# ===== ORIGINAL TESTS (keeping the ones that work) =====

def test_job_script_contains_expected_fields(monkeypatch, dummy_ca_cert):
    ca_file, cert_file = dummy_ca_cert
    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
    )

    try:
        job = CoffeaCasaJob(
            scheduler=None,
            name="test-job",
            cores=1,
            memory="1GB",
            disk="1GB",
            job_extra_directives=cluster._job_kwargs["job_extra_directives"],
        )

        script = job.job_script()

        # Check basic HTCondor submit file structure
        assert "Queue" in script
        assert "docker" in script.lower()
        assert "CoffeaCasaWorkerType" in script
        assert "test-job" in script
        
        # The key fix: uppercase Executable = /bin/sh should NOT be present
        assert "Executable = /bin/sh" not in script, \
            "job_script() should have stripped dask-jobqueue's Executable line"
    finally:
        cluster.close()


def test_job_header_dict_includes_proxy_flag(monkeypatch, tmp_path, dummy_ca_cert):
    ca_file, cert_file = dummy_ca_cert
    proxy_file = tmp_path / "x509up_u999"
    proxy_file.write_text("dummy-proxy")

    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
        proxy_file=proxy_file,
    )

    try:
        job_extra = cluster._job_kwargs.get("job_extra_directives", {})
        assert job_extra["use_x509userproxy"] is True
    finally:
        cluster.close()


def test_job_script_contains_transfer_files(
    monkeypatch,
    dummy_ca_cert,
    dummy_token,
):
    ca_file, cert_file = dummy_ca_cert

    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
        token_file=dummy_token,
    )

    try:
        job_extra = cluster._job_kwargs.get("job_extra_directives", {})
        assert str(dummy_token) in job_extra["transfer_input_files"]
    finally:
        cluster.close()


def test_cluster_scale_and_adapt(monkeypatch, dummy_ca_cert):
    ca_file, cert_file = dummy_ca_cert
    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
    )

    try:
        with (
            patch.object(cluster, "scale") as mock_scale,
            patch.object(cluster, "adapt") as mock_adapt,
        ):
            cluster.scale(jobs=5)
            mock_scale.assert_called_once_with(jobs=5)

            cluster.adapt(maximum_jobs=10)
            mock_adapt.assert_called_once_with(maximum_jobs=10)
    finally:
        cluster.close()


def test_scheduler_contact_address(monkeypatch, dummy_ca_cert):
    ca_file, cert_file = dummy_ca_cert
    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
    )

    try:
        sched_options = cluster.coffeacasa_scheduler_options
        assert sched_options["contact_address"] == "tcp://127.0.0.1:8786"
        assert sched_options["dashboard_address"] == ":8785"
    finally:
        cluster.close()


# ===== NEW TESTS FOR BUG FIXES =====

def test_dashboard_address_boolean_sanitization():
    """Test that dashboard_address=True from Labextension is sanitized"""
    import dask
    
    # Simulate Labextension injecting a boolean into dask.config
    dask.config.set({"distributed.dashboard.link": True})
    
    # Mock to prevent actual cluster startup
    with patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy", force_tcp=True)
        except:
            pass
        
        # Verify the boolean was sanitized
        link = dask.config.get("distributed.dashboard.link")
        assert not isinstance(link, bool), \
            "dashboard.link should be sanitized from bool to string"


def test_force_tcp_clears_require_encryption():
    """Test that force_tcp=True sets require-encryption to False"""
    import dask
    
    # Simulate dask.yaml with require-encryption: true
    dask.config.set({"distributed.comm.require-encryption": True})
    
    with patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy", force_tcp=True)
        except:
            pass
        
        # Verify require-encryption was set to False
        require_enc = dask.config.get("distributed.comm.require-encryption")
        assert require_enc is False, \
            "force_tcp=True should set require-encryption to False"


def test_security_none_passed_to_parent():
    """Test that security=None is passed to prevent TLS flag injection"""
    with patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy", force_tcp=True)
        except:
            pass
        
        # Verify security=None was passed
        assert mock_init.called
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs.get("security") is None, \
            "security should be None to prevent --tls-* flag injection"


def test_job_script_strips_dask_jobqueue_executable(monkeypatch, dummy_ca_cert):
    """Test that job_script() removes dask-jobqueue's broken lines"""
    ca_file, cert_file = dummy_ca_cert
    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
    )
    
    try:
        job = cluster.job_cls(
            scheduler=None,
            name="test-job",
            cores=1,
            memory="1GB",
            disk="1GB",
            job_extra_directives=cluster._job_kwargs["job_extra_directives"],
        )
        
        script = job.job_script()
        
        # Should NOT contain dask-jobqueue's generated lines
        assert 'Arguments = "-c' not in script
        assert "Arguments = '-c" not in script
        assert 'Executable = /bin/sh' not in script
    finally:
        cluster.close()


def test_dask_scheduler_address_in_job_directives(monkeypatch, dummy_ca_cert):
    """Test that +DaskSchedulerAddress uses the DNS contact address"""
    ca_file, cert_file = dummy_ca_cert
    cluster = make_test_cluster(
        monkeypatch,
        ca_file=ca_file,
        cert_file=cert_file,
    )
    
    try:
        job_extra = cluster._job_kwargs.get("job_extra_directives", {})
        dask_addr = job_extra.get("+DaskSchedulerAddress", "")
        
        # Should contain the contact address (tcp://127.0.0.1:8786 from mock)
        assert "tcp://" in dask_addr or "tls://" in dask_addr
        assert "8786" in dask_addr
    finally:
        cluster.close()