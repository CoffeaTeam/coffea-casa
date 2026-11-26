"""Tests for coffea_casa.taskvine (TaskVine workers on HTCondor, #167)"""
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import dask
import pytest

import coffea_casa.config  # noqa: F401 - registers jobqueue.coffea-casa defaults
from coffea_casa.taskvine import (
    VINE_CONTAINER_PORT,
    CoffeaCasaVineWorkers,
    _check_port_free,
)

IMAGE = "hub.opensciencegrid.org/coffea-casa/cc-analysis-alma9:test"


def _manager(port=8786, ssl=True):
    return SimpleNamespace(port=port, using_ssl=ssl)


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Notebook-like environment: routed hostname, a token, no proxy"""
    monkeypatch.delenv("POD_IP", raising=False)
    monkeypatch.setenv("HOST_IP", "jane.dask.coffea.casa")
    monkeypatch.setenv("XCACHE_HOST", "xcache.example.org")
    monkeypatch.setenv("JUPYTERHUB_API_TOKEN", "secret")
    token = tmp_path / "access_token"
    token.write_text("t")
    with patch("coffea_casa.taskvine.bearer_token_path", return_value=str(token)), \
         patch("coffea_casa.taskvine.x509_user_proxy_path", return_value=None):
        yield SimpleNamespace(token=token, logs=tmp_path / "logs")


def _workers(env, config=None, **kwargs):
    kwargs.setdefault("worker_image", IMAGE)
    kwargs.setdefault("log_directory", env.logs)
    with dask.config.set(config or {}):
        return CoffeaCasaVineWorkers(_manager(), **kwargs)


def test_jobs_start_vine_worker_against_this_notebook(env):
    d = _workers(env, cores=4, memory_mb=8000, disk_mb=16000).directives
    assert d["+CoffeaCasaWorkerType"] == '"taskvine"'
    assert d["+VineManagerAddress"] == '"jane.dask.coffea.casa:8786"'
    assert d["universe"] == "docker"
    assert d["docker_image"] == IMAGE
    assert d["container_service_names"] == "vine"
    assert d["vine_container_port"] == VINE_CONTAINER_PORT
    assert (d["request_cpus"], d["request_memory"], d["request_disk"]) == (4, 8000, 16000 * 1024)
    assert d["+VineWorkerTimeout"] == 900


def test_token_is_sent_encrypted(env):
    d = _workers(env).directives
    assert str(env.token) in d["transfer_input_files"]
    assert str(env.token) in d["encrypt_input_files"]


def test_site_config_applies_but_cannot_drop_encryption(env):
    d = _workers(env, {
        "jobqueue.coffea-casa.job-extra-directives": {
            "+AccountingGroup": '"group_atlas.af"',
            "encrypt_input_files": "",
        },
    }).directives
    assert d["+AccountingGroup"] == '"group_atlas.af"'
    assert str(env.token) in d["encrypt_input_files"]


def test_notebook_environment_is_not_copied(env):
    """Only the site passthrough variables reach the job, never getenv"""
    w = _workers(env)
    assert "getenv" not in w.directives
    assert "XCACHE_HOST=xcache.example.org" in w.directives["environment"]
    assert "JUPYTERHUB_API_TOKEN" not in w.submit_description(1)


def test_worker_image_defaults_to_config(env):
    w = _workers(env, {"jobqueue.coffea-casa.worker-image": "img:cfg"}, worker_image=None)
    assert w.directives["docker_image"] == "img:cfg"


def test_manager_without_tls_is_rejected(env):
    with pytest.raises(ValueError, match="TLS"):
        CoffeaCasaVineWorkers(_manager(ssl=False), worker_image=IMAGE)


def test_submit_description_queues_n_workers(env):
    text = _workers(env).submit_description(3)
    assert text.splitlines()[-1] == "queue 3"
    assert "use_x509userproxy = false" in text
    assert "+CoffeaCasaWorkerType = \"taskvine\"" in text


def test_submit_spools_and_records_the_cluster(env):
    w = _workers(env)
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        with open(cmd[-1]) as f:
            seen["text"] = f.read()
        return MagicMock(returncode=0, stdout="2 job(s) submitted to cluster 4242.\n", stderr="")

    with patch("coffea_casa.taskvine.subprocess.run", side_effect=fake_run):
        assert w.submit(2) == 4242
    assert seen["cmd"][:2] == ["condor_submit", "-spool"]
    assert seen["text"].endswith("queue 2\n")
    assert w.job_ids == [4242]
    assert env.logs.is_dir()


def test_submit_failure_raises(env):
    w = _workers(env)
    with patch("coffea_casa.taskvine.subprocess.run",
               return_value=MagicMock(returncode=1, stdout="", stderr="no schedd")):
        with pytest.raises(RuntimeError, match="no schedd"):
            w.submit(1)


def test_close_removes_only_this_objects_jobs(env):
    w = _workers(env)
    with patch("coffea_casa.taskvine.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="", stderr="")) as run:
        w.close()
    assert run.call_args[0][0] == [
        "condor_rm", "-constraint", f'CoffeaCasaClusterId == "{w.cluster_id}"']


def test_fetch_worker_logs_selects_vine_logs(env):
    w = _workers(env)
    env.logs.mkdir()
    (env.logs / "vine-worker-1.0.err").write_text("boom")
    (env.logs / "worker-2.0.err").write_text("a dask worker's")
    with patch("coffea_casa.coffea_casa.subprocess.run",
               return_value=MagicMock(returncode=0, stdout="", stderr="")) as run:
        files = w.fetch_worker_logs()
    assert f'CoffeaCasaClusterId == "{w.cluster_id}"' in run.call_args[0][0][2]
    assert files == [env.logs / "vine-worker-1.0.err"]


def test_port_in_use_explains_the_dask_conflict():
    with socket.socket() as s:
        s.bind(("0.0.0.0", 0))
        s.listen()
        with pytest.raises(RuntimeError, match="Dask cluster"):
            _check_port_free(s.getsockname()[1])
