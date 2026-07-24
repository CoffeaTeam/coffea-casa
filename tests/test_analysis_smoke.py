"""Smoke tests executed *inside* the analysis / dask-worker image.

Run with:  docker run --rm -e COFFEA_CASA_ANALYSIS_TESTS=1 \
             -v $PWD/tests:/tests:ro IMAGE python -m pytest /tests -v

This is the worker counterpart to test_image_smoke.py. It asserts only what the
SLIM image is supposed to have — the HEP/dask stack, the XRootD xcache plugin,
the patched distributed (CalVer only), supervisor, and a working `dask worker`
CLI. It deliberately does NOT check the notebook stack (jupyterlab,
dask_labextension, /opt/dask, live kernels), which the worker image omits.

Gated on COFFEA_CASA_ANALYSIS_TESTS=1 (a different flag than the singleuser
suite) so that when both files are mounted in /tests, each CI step runs only its
own: the singleuser step sets COFFEA_CASA_IMAGE_TESTS=1, the analysis step sets
COFFEA_CASA_ANALYSIS_TESTS=1.

Flavour context comes from env vars set per matrix row:
    CASA_FLAVOUR  e.g. "noml" | "dak" | "full" | "0.7"
    CASA_PYVER    e.g. "3.12" | "3.11"
    CASA_COMBINE  "1" for cc-analysis-combine-alma9, else "0"
"""
import importlib
import os
import pwd
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("COFFEA_CASA_ANALYSIS_TESTS") != "1",
    reason="analysis smoke tests: set COFFEA_CASA_ANALYSIS_TESTS=1 and run inside "
    "the coffea-casa analysis (worker) image",
)

CASA_FLAVOUR = os.environ.get("CASA_FLAVOUR", "noml")
CASA_PYVER = os.environ.get("CASA_PYVER", "3.12")
CASA_COMBINE = os.environ.get("CASA_COMBINE", "0") == "1"
IS_07 = CASA_FLAVOUR == "0.7"

# Worker-relevant imports only. No jupyter / dask_labextension here — the slim
# image does not ship them.
CRITICAL_IMPORTS = [
    "coffea",
    "dask",
    "distributed",
    "coffea_casa",
    "uproot",
    "awkward",
    "numpy",
    "numba",
    "pyhf",
    "cabinetry",
    "servicex",
    "s3fs",
    "mlflow",
    "aiostream",
]


@pytest.mark.parametrize("module", CRITICAL_IMPORTS)
def test_import(module):
    importlib.import_module(module)


def test_numpy_pin():
    import numpy
    v = numpy.__version__
    major = int(v.split(".")[0])
    if IS_07:
        assert major < 2, (
            f"0.7 image expects numpy<2, got {v} "
            "(something pulled in a numpy 2.x after the pin)"
        )
    else:
        expected = os.environ.get("CASA_NUMPY_EXACT", "2.4.2")
        assert v == expected, (
            f"numpy pin broken: got {v}, expected {expected}"
        )


def test_python_version():
    want = tuple(int(x) for x in CASA_PYVER.split("."))
    assert sys.version_info[:2] == want, (
        f"Python is {sys.version.split()[0]} but this flavour "
        f"({CASA_FLAVOUR}) expects python{CASA_PYVER}"
    )


def test_patched_distributed_is_the_imported_one():
    # CalVer-only, like the notebook image; skipped for 0.7.
    if IS_07:
        pytest.skip("distributed patch intentionally skipped for the 0.7 flavour")
    import distributed
    expected = f"/usr/local/lib/python{CASA_PYVER}/site-packages/distributed"
    actual = os.path.dirname(distributed.__file__)
    assert actual == expected, (
        f"distributed imported from {actual}, not the patched copy at {expected}"
    )


def test_xrootd_plugin_env():
    plugin = os.environ.get("XRD_PLUGIN", "")
    confdir = os.environ.get("XRD_PLUGINCONFDIR", "")
    assert plugin and os.path.exists(plugin), f"XRD_PLUGIN missing: {plugin!r}"
    assert confdir, "XRD_PLUGINCONFDIR not set"


def test_supervisor_available():
    # The worker is launched under supervisord (k8s-worker/supervisord.conf).
    assert shutil.which("supervisord"), "supervisord missing from PATH"
    assert os.path.exists("/etc/supervisor/supervisord.conf"), (
        "supervisord.conf not installed at /etc/supervisor/"
    )


def test_dask_worker_cli_runs():
    """The whole point of the image: it can launch a dask worker."""
    exe = shutil.which("dask")
    assert exe, "`dask` CLI missing from PATH"
    out = subprocess.run(
        [exe, "worker", "--help"], capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr


def test_running_as_nb_user():
    assert os.getuid() == 6440, f"expected UID 6440 (cms-jovyan), got {os.getuid()}"
    assert pwd.getpwuid(os.getuid()).pw_name == "cms-jovyan"


def test_home_is_writable():
    home = os.path.expanduser("~")
    probe = os.path.join(home, ".ci-write-probe")
    with open(probe, "w") as f:
        f.write("ok")
    os.remove(probe)


def test_combine_tools_present():
    """cc-analysis-combine-alma9 must ship ROOT + the `combine` binary."""
    if not CASA_COMBINE:
        pytest.skip("not a combine image")
    import ROOT  # noqa: F401  (provided by the conda `root` package)
    assert shutil.which("combine"), (
        "`combine` binary missing — cms-combine did not install correctly"
    )
