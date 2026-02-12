import os
import pytest
import warnings
from pathlib import Path
from unittest.mock import patch

from coffea_casa import CoffeaCasaCluster, CoffeaCasaJob
from distributed.security import Security


# -----------------------------
# Fixtures
# -----------------------------

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


# -----------------------------
# Helper
# -----------------------------

def make_test_cluster(
    monkeypatch,
    *,
    ca_file=None,
    cert_file=None,
    token_file=None,
    proxy_file=None,
):
    """Create a CoffeaCasaCluster with patched Security."""

    monkeypatch.setenv("HOST_IP", "127.0.0.1")

    if token_file:
        monkeypatch.setenv("BEARER_TOKEN_FILE", str(token_file))

    if proxy_file:
        monkeypatch.setenv("X509_USER_PROXY", str(proxy_file))

    # Patch Security where it is USED
    with patch(
        "coffea_casa.coffea_casa.Security",
        lambda **kwargs: Security(require_encryption=False),
    ):
        cluster = CoffeaCasaCluster(worker_image="dummy/image")

        # Override cert paths on the instance
        if ca_file:
            cluster.ca_file = ca_file
        if cert_file:
            cluster.cert_file = cert_file

    return cluster


# -----------------------------
# Tests
# -----------------------------

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

        assert "Executable" in script
        assert "Arguments" in script
        assert "Queue" in script
        assert "docker" in script.lower()
        assert "CoffeaCasaWorkerType" in script
        assert "test-job" in script
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
        job = cluster.job_cls(
            scheduler=None,
            name="test-job-proxy",
            **cluster._job_kwargs,
        )

        assert job.job_extra_directives["use_x509userproxy"] is True
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
        job = cluster.job_cls(
            scheduler=None,
            name="test-job-token",
            **cluster._job_kwargs,
        )
    finally:
        cluster.close()

    job_directives = job.job_extra_directives
    assert str(dummy_token) in job_directives["transfer_input_files"]


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
