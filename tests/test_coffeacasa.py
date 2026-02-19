import os
import sys
import pytest
import warnings
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path to find coffea_casa
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from coffea_casa import (
        CoffeaCasaCluster, 
        CoffeaCasaJob,
        bearer_token_path,
        x509_user_proxy_path,
        security_obj,
    )
except ImportError:
    # Try alternate import if in package structure
    from coffea_casa.coffea_casa import (
        CoffeaCasaCluster, 
        CoffeaCasaJob,
        bearer_token_path,
        x509_user_proxy_path,
        security_obj,
    )

from distributed.security import Security


@pytest.fixture(autouse=True)
def suppress_unraisable_warnings():
    warnings.filterwarnings(
        "ignore",
        category=pytest.PytestUnraisableExceptionWarning,
    )


@pytest.fixture
def dummy_certs(tmp_path):
    """Create dummy CA and host cert files"""
    ca_file = tmp_path / "ca.pem"
    cert_file = tmp_path / "hostcert.pem"
    key_file = tmp_path / "hostkey.pem"
    
    # Combined cert+key bundle
    ca_file.write_text("-----BEGIN CERTIFICATE-----\nfake-ca\n-----END CERTIFICATE-----")
    cert_file.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nfake-key\n-----END RSA PRIVATE KEY-----\n"
        "-----BEGIN CERTIFICATE-----\nfake-cert\n-----END CERTIFICATE-----"
    )
    key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\nfake-key\n-----END RSA PRIVATE KEY-----")
    
    return ca_file, cert_file, key_file


@pytest.fixture
def mock_environment(monkeypatch, tmp_path):
    """Set up mock environment variables"""
    monkeypatch.setenv("HOST_IP", "127.0.0.1")
    monkeypatch.setenv("POD_IP", "192.168.1.100")
    return tmp_path


@pytest.fixture
def mock_security():
    """Create a mock Security object"""
    mock_sec = MagicMock(spec=Security)
    mock_sec.get_connection_args.return_value = {
        "require_encryption": False,
        "ssl_context": None,
    }
    return mock_sec


# ===== Tests for helper functions =====

def test_bearer_token_path_from_env(monkeypatch, tmp_path):
    """Test bearer token path resolution from BEARER_TOKEN_FILE env var"""
    token_file = tmp_path / "token.txt"
    token_file.write_text("fake-token")
    
    monkeypatch.setenv("BEARER_TOKEN_FILE", str(token_file))
    
    # Mock Path to recognize the token file
    existing_paths = {str(token_file)}
    
    class MockPath:
        def __init__(self, path):
            self.path = str(path)
        
        def is_file(self):
            return self.path in existing_paths
        
        def __str__(self):
            return self.path
    
    with patch("coffea_casa.coffea_casa.Path", MockPath):
        result = bearer_token_path()
        assert result == str(token_file)


def test_bearer_token_path_from_cmsaf_secrets(monkeypatch, tmp_path):
    """Test bearer token path resolution from /etc/cmsaf-secrets-chown"""
    expected_path = "/etc/cmsaf-secrets-chown/access_token"
    
    # Clear env vars to force checking cmsaf-secrets
    monkeypatch.delenv("BEARER_TOKEN_FILE", raising=False)
    
    # Create a set of paths that should exist
    existing_paths = {expected_path}
    
    # Mock Path.is_file to return True only for paths in our set
    class MockPath:
        def __init__(self, path):
            self.path = str(path)
        
        def is_file(self):
            return self.path in existing_paths
        
        def __str__(self):
            return self.path
    
    with patch("coffea_casa.coffea_casa.Path", MockPath):
        result = bearer_token_path()
        assert result == expected_path


def test_bearer_token_path_from_tmp(monkeypatch, tmp_path):
    """Test bearer token path resolution from /tmp/bt_u$UID"""
    uid = os.geteuid()
    expected_path = f"/tmp/bt_u{uid}"
    
    # Clear env vars to force fallback to /tmp
    monkeypatch.delenv("BEARER_TOKEN_FILE", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    
    # Create a set of paths that should exist
    existing_paths = {expected_path}
    
    # Mock Path.is_file to return True only for paths in our set
    original_path = Path
    class MockPath:
        def __init__(self, path):
            self.path = str(path)
        
        def is_file(self):
            return self.path in existing_paths
        
        def __str__(self):
            return self.path
    
    with patch("coffea_casa.coffea_casa.Path", MockPath):
        result = bearer_token_path()
        assert result == expected_path


def test_x509_user_proxy_path_from_env(monkeypatch, tmp_path):
    """Test X.509 proxy path from environment variable"""
    proxy_file = tmp_path / "x509_proxy"
    proxy_file.write_text("fake-proxy")
    
    monkeypatch.setenv("X509_USER_PROXY", str(proxy_file))
    
    # Mock Path to recognize the proxy file
    existing_paths = {str(proxy_file)}
    
    class MockPath:
        def __init__(self, path):
            self.path = str(path)
        
        def is_file(self):
            return self.path in existing_paths
        
        def __str__(self):
            return self.path
    
    with patch("coffea_casa.coffea_casa.Path", MockPath):
        result = x509_user_proxy_path()
        assert result == str(proxy_file)


def test_x509_user_proxy_path_default(monkeypatch, tmp_path):
    """Test X.509 proxy path from default location"""
    uid = os.geteuid()
    expected_path = f"/tmp/x509up_u{uid}"
    
    monkeypatch.delenv("X509_USER_PROXY", raising=False)
    
    # Mock Path.is_file to return True for the default proxy path
    existing_paths = {expected_path}
    
    class MockPath:
        def __init__(self, path):
            self.path = str(path)
        
        def is_file(self):
            return self.path in existing_paths
        
        def __str__(self):
            return self.path
    
    with patch("coffea_casa.coffea_casa.Path", MockPath):
        result = x509_user_proxy_path()
        assert result == expected_path


def test_x509_user_proxy_path_not_found(monkeypatch):
    """Test X.509 proxy path when file doesn't exist"""
    monkeypatch.delenv("X509_USER_PROXY", raising=False)
    
    # Mock Path.is_file to always return False
    class MockPath:
        def __init__(self, path):
            self.path = str(path)
        
        def is_file(self):
            return False
        
        def __str__(self):
            return self.path
    
    with patch("coffea_casa.coffea_casa.Path", MockPath):
        result = x509_user_proxy_path()
        assert result is None


# ===== Tests for CoffeaCasaCluster initialization =====

def test_dashboard_address_boolean_sanitization(mock_environment):
    """Test that dashboard_address=True from Labextension is sanitized"""
    import dask
    
    # Simulate Labextension injecting a boolean
    dask.config.set({"distributed.dashboard.link": True})
    
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy")
        except:
            pass
        
        # Verify boolean was sanitized
        link = dask.config.get("distributed.dashboard.link")
        assert not isinstance(link, bool), \
            "dashboard.link should be sanitized from bool to string"


def test_force_tcp_clears_require_encryption(mock_environment):
    """Test that force_tcp=True sets require-encryption to False"""
    import dask
    
    dask.config.set({"distributed.comm.require-encryption": True})
    
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy", force_tcp=True)
        except:
            pass
        
        require_enc = dask.config.get("distributed.comm.require-encryption")
        assert require_enc is False, \
            "force_tcp=True should set require-encryption to False"


def test_worker_tls_config_patched_when_null(mock_environment, dummy_certs):
    """Test that null worker.cert/key in dask.config get patched"""
    ca_file, cert_file, key_file = dummy_certs
    import dask
    
    dask.config.set({
        "distributed.comm.require-encryption": True,
        "distributed.comm.tls.worker.cert": None,
        "distributed.comm.tls.worker.key": None,
    })
    
    with patch("coffea_casa.coffea_casa.CA_FILE", ca_file), \
         patch("coffea_casa.coffea_casa.CERT_FILE", cert_file), \
         patch("coffea_casa.coffea_casa.KEY_FILE", key_file), \
         patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy")
        except:
            pass
        
        # Verify worker cert/key were patched
        worker_cert = dask.config.get("distributed.comm.tls.worker.cert")
        worker_key = dask.config.get("distributed.comm.tls.worker.key")
        assert worker_cert is not None, "worker.cert should be patched"
        assert worker_key is not None, "worker.key should be patched"


def test_port_conflict_check_disabled_by_default(mock_environment):
    """Test that port conflict check is disabled by default"""
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init, \
         patch("socket.socket") as mock_socket:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        try:
            CoffeaCasaCluster(worker_image="dummy")
        except:
            pass
        
        # Socket should not be called when check_ports=False (default)
        assert not mock_socket.called, \
            "Port check should be disabled by default"


def test_port_conflict_check_when_enabled(mock_environment):
    """Test that port conflict check works when enabled"""
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        # Should raise if port is in use
        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.__enter__.return_value.bind.side_effect = OSError()
            
            with pytest.raises(RuntimeError, match="Port .* already in use"):
                CoffeaCasaCluster(worker_image="dummy", check_ports=True)


# ===== Tests for job configuration =====

def test_job_extra_directives_contains_required_fields(mock_environment):
    """Test that job_extra_directives contains all required HTCondor fields"""
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        cluster = CoffeaCasaCluster(worker_image="dummy")
        
        # Get the job kwargs that were passed to parent
        assert mock_init.called
        job_kwargs = mock_init.call_args[1]
        
        directives = job_kwargs.get("job_extra_directives", {})
        
        assert "universe" in directives
        assert directives["universe"] == "docker"
        assert "docker_image" in directives
        assert "container_service_names" in directives
        assert directives["container_service_names"] == "dask,nanny"
        assert "+CoffeaCasaWorkerType" in directives
        assert "+DaskSchedulerAddress" in directives
        assert "transfer_input_files" in directives
        assert "encrypt_input_files" in directives


def test_scheduler_address_uses_contact_address(mock_environment):
    """Test that +DaskSchedulerAddress uses the contact address"""
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        cluster = CoffeaCasaCluster(worker_image="dummy")
        
        job_kwargs = mock_init.call_args[1]
        directives = job_kwargs.get("job_extra_directives", {})
        
        dask_addr = directives.get("+DaskSchedulerAddress", "")
        # Should contain protocol and port
        assert "://" in dask_addr or "tcp" in dask_addr.lower() or "tls" in dask_addr.lower()
        assert "8786" in dask_addr


def test_tls_mode_includes_cert_files(mock_environment, dummy_certs):
    """Test that TLS mode includes cert files in transfer_input_files"""
    ca_file, cert_file, key_file = dummy_certs
    
    with patch("coffea_casa.coffea_casa.CA_FILE", ca_file), \
         patch("coffea_casa.coffea_casa.CERT_FILE", cert_file), \
         patch("coffea_casa.coffea_casa.KEY_FILE", key_file), \
         patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": True}
        mock_init.return_value = None
        
        cluster = CoffeaCasaCluster(worker_image="dummy")
        
        job_kwargs = mock_init.call_args[1]
        directives = job_kwargs.get("job_extra_directives", {})
        
        transfer_files = directives.get("transfer_input_files", "")
        assert str(ca_file) in transfer_files or "ca.pem" in transfer_files
        assert str(cert_file) in transfer_files or "hostcert.pem" in transfer_files


def test_tcp_mode_excludes_cert_files(mock_environment):
    """Test that TCP mode (force_tcp=True) excludes cert files"""
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        cluster = CoffeaCasaCluster(worker_image="dummy", force_tcp=True)
        
        job_kwargs = mock_init.call_args[1]
        directives = job_kwargs.get("job_extra_directives", {})
        
        transfer_files = directives.get("transfer_input_files", "")
        # Should not contain cert files
        assert "ca.pem" not in transfer_files
        assert "hostcert.pem" not in transfer_files


def test_scheduler_options_include_protocol(mock_environment):
    """Test that scheduler options include correct protocol"""
    with patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        cluster = CoffeaCasaCluster(worker_image="dummy", force_tcp=True)
        
        job_kwargs = mock_init.call_args[1]
        sched_opts = job_kwargs.get("scheduler_options", {})
        
        assert "protocol" in sched_opts
        assert sched_opts["protocol"] == "tcp"  # force_tcp=True
        assert "contact_address" in sched_opts
        assert "port" in sched_opts
        assert sched_opts["port"] == 8786


def test_x509_proxy_detected(mock_environment, tmp_path):
    """Test that X.509 proxy is detected and use_x509userproxy is set"""
    proxy_file = tmp_path / "x509_proxy"
    proxy_file.write_text("fake-proxy")
    
    with patch("coffea_casa.coffea_casa.x509_user_proxy_path") as mock_proxy, \
         patch("coffea_casa.coffea_casa.security_obj") as mock_sec_obj, \
         patch("coffea_casa.coffea_casa.HTCondorCluster.__init__") as mock_init:
        
        mock_proxy.return_value = str(proxy_file)
        mock_sec_obj.return_value = MagicMock(spec=Security)
        mock_sec_obj.return_value.get_connection_args.return_value = {"require_encryption": False}
        mock_init.return_value = None
        
        cluster = CoffeaCasaCluster(worker_image="dummy")
        
        job_kwargs = mock_init.call_args[1]
        directives = job_kwargs.get("job_extra_directives", {})
        
        assert directives.get("use_x509userproxy") is True