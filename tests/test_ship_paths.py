"""ship_paths: local code (files and packages) made importable on workers.

Covers https://github.com/CoffeaTeam/coffea-casa/issues/112: a processor
defined in a local module or package next to the notebook must import on the
workers, including from subpackages (``from myanalysis.sub import mod``).
"""
import importlib
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from coffea_casa.coffea_casa import CoffeaCasaCluster
from coffea_casa.env_pack import ShippedEnv

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER_ARGS = REPO_ROOT / "docker" / "prepare-env" / "worker-args.sh"
# Unique so it can't collide with anything installed in the test env
PKG = "cc112_myanalysis"


@pytest.fixture(autouse=True)
def no_env_shipping():
    with patch("coffea_casa.coffea_casa.prepare_shipped_env", return_value=None):
        yield


def make_analysis(root):
    """A notebook directory with a loose module and a nested package."""
    pkg = root / PKG / "sub"
    pkg.mkdir(parents=True)
    (root / PKG / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(textwrap.dedent("""
        class NanoProcessor:
            def __init__(self, factor):
                self.factor = factor

            def process(self, x):
                return x * self.factor

        def double(x):
            return 2 * x
    """))
    (root / "cc112_helpers.py").write_text("def triple(x):\n    return 3 * x\n")
    return root


def job_directives(ship_paths, **kwargs):
    job_kwargs = CoffeaCasaCluster._modify_job_kwargs(
        {}, force_tcp=True, ship_paths=ship_paths, **kwargs)
    return job_kwargs["job_extra_directives"]


# ===== job configuration =====

def test_ship_paths_are_transferred_with_names_attr(tmp_path, monkeypatch):
    make_analysis(tmp_path)
    monkeypatch.chdir(tmp_path)

    directives = job_directives(["cc112_helpers.py", f"{PKG}/"])
    for name in ("cc112_helpers.py", PKG):
        assert str(tmp_path.resolve() / name) in directives["transfer_input_files"]
    assert directives["+CoffeaCasaShippedPaths"] == f'"cc112_helpers.py,{PKG}"'


def test_single_path_string_is_accepted(tmp_path, monkeypatch):
    make_analysis(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert job_directives("cc112_helpers.py")["+CoffeaCasaShippedPaths"] == '"cc112_helpers.py"'


def test_no_ship_paths_sets_no_attr():
    assert "+CoffeaCasaShippedPaths" not in job_directives(None)


def test_missing_path_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="nope.py"):
        job_directives(["nope.py"])


def test_duplicate_names_raise(tmp_path):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "utils.py").write_text("")
    with pytest.raises(ValueError, match="'utils.py' is already used"):
        job_directives([tmp_path / "a" / "utils.py", tmp_path / "b" / "utils.py"])


def test_reserved_name_raises(tmp_path):
    (tmp_path / "requirements.txt").write_text("")
    with pytest.raises(ValueError, match="already used"):
        job_directives([tmp_path / "requirements.txt"])


def test_clash_with_shipped_env_raises(tmp_path):
    (tmp_path / "cc-env-foo-abc.tar.gz").write_text("")
    shipped = ShippedEnv(tmp_path / "other" / "cc-env-foo-abc.tar.gz")
    with patch("coffea_casa.coffea_casa.prepare_shipped_env", return_value=shipped):
        with pytest.raises(ValueError, match="already used"):
            job_directives([tmp_path / "cc-env-foo-abc.tar.gz"])


# ===== end to end: real scheduler + worker set up by worker-args.sh =====

def condor_transfer(paths, iwd):
    """What HTCondor does with transfer_input_files: copy by base name."""
    iwd.mkdir()
    for path in paths:
        path = Path(path)
        if path.is_dir():
            shutil.copytree(path, iwd / path.name)
        else:
            shutil.copy(path, iwd / path.name)


def worker_env(job_ad, iwd, setup_shipped_paths=True):
    """The environment prepare-env-cc-analysis.sh gives the dask worker."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if setup_shipped_paths:
        out = subprocess.run(
            ["bash", "-c", 'source "$0" && cc_setup_shipped_paths "$1" "$2" '
                           '&& echo "PYTHONPATH=$PYTHONPATH"',
             WORKER_ARGS, job_ad, iwd],
            capture_output=True, text=True, check=True).stdout
        env["PYTHONPATH"] = out.strip().rsplit("PYTHONPATH=", 1)[1]
    return env


@pytest.fixture
def scheduler_and_worker(tmp_path, monkeypatch):
    """Yield start_worker(**worker_env kwargs) -> Client; cleans everything up."""
    distributed = pytest.importorskip("distributed")
    if shutil.which("bash") is None:
        pytest.skip("bash needed to run worker-args.sh")

    notebook = make_analysis(tmp_path / "notebook")
    monkeypatch.chdir(notebook)
    directives = job_directives(["cc112_helpers.py", PKG])
    job_ad = tmp_path / "job.ad"
    job_ad.write_text("CoffeaCasaShippedPaths = "
                      f"{directives['+CoffeaCasaShippedPaths']}\n")
    iwd = tmp_path / "iwd"
    condor_transfer(
        [p.strip() for p in directives["transfer_input_files"].split(",") if p.strip()],
        iwd)
    # The notebook (client) side imports from its own directory
    monkeypatch.syspath_prepend(str(notebook))

    cluster = distributed.LocalCluster(n_workers=0, protocol="tcp",
                                       dashboard_address=None)
    client = distributed.Client(cluster)
    procs = []
    worker_cwd = tmp_path / "worker-cwd"
    worker_cwd.mkdir()

    def start_worker(**kwargs):
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "distributed.cli.dask_worker",
             cluster.scheduler_address, "--nthreads", "1", "--no-dashboard"],
            env=worker_env(job_ad, iwd, **kwargs), cwd=worker_cwd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        client.wait_for_workers(1, timeout=60)
        return client

    yield start_worker
    client.close()
    cluster.close()
    for proc in procs:
        proc.terminate()
        proc.wait(timeout=30)
    for mod in [m for m in sys.modules if m.startswith((PKG, "cc112_helpers"))]:
        del sys.modules[mod]


def test_shipped_code_imports_on_worker(scheduler_and_worker):
    client = scheduler_and_worker()
    import cc112_helpers
    from cc112_myanalysis.sub import mod

    # Functions and a processor instance are pickled by reference to their
    # modules, so the worker has to import them from the shipped paths.
    client.run(importlib.import_module, f"{PKG}.sub.mod")
    assert client.submit(mod.double, 21).result(timeout=60) == 42
    assert client.submit(cc112_helpers.triple, 2).result(timeout=60) == 6
    processor = mod.NanoProcessor(10)
    assert client.submit(processor.process, 4).result(timeout=60) == 40


def test_without_shipped_paths_worker_cannot_import(scheduler_and_worker):
    """Control: the same worker without cc_setup_shipped_paths fails (#112)."""
    client = scheduler_and_worker(setup_shipped_paths=False)
    # The client imports fine; the worker can't
    importlib.import_module(f"{PKG}.sub.mod")
    with pytest.raises(ModuleNotFoundError, match=PKG):
        client.run(importlib.import_module, f"{PKG}.sub.mod")
