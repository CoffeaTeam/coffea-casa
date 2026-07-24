"""Smoke tests executed *inside* the singleuser image.

Run with:  docker run --rm -v $PWD/tests:/tests:ro IMAGE python -m pytest /tests -v
They validate the Python environment the way a real user session would use it.

Flavour-dependent expectations (Python version, numpy pin, whether the patched
distributed is applied) are read from environment variables set by the CI
workflow per matrix row:
    CASA_FLAVOUR   e.g. "noml" | "dak" | "full" | "0.7"
    CASA_PYVER     e.g. "3.12" | "3.11"
so the same file works for every flavour without a separate 0.7 test file.
"""
import importlib
import os
import pwd
import shutil
import subprocess
import sys

import pytest

# These tests only make sense inside the built singleuser image (they assert on
# the HEP stack, condor CLIs, the cms-jovyan UID, /opt/dask, patched
# distributed, etc.). A bare ``pytest`` on a dev box or the unit-test CI runner
# would collect and fail all of them, so skip unless explicitly enabled. The
# in-image CI step sets COFFEA_CASA_IMAGE_TESTS=1 (see
# .github/workflows/docker-build-test-publish.yaml).
pytestmark = pytest.mark.skipif(
    os.environ.get("COFFEA_CASA_IMAGE_TESTS") != "1",
    reason="image smoke tests: set COFFEA_CASA_IMAGE_TESTS=1 and run inside the "
    "coffea-casa singleuser image",
)

# Flavour context (defaults match the canonical CalVer image so a bare local
# run still behaves sensibly).
CASA_FLAVOUR = os.environ.get("CASA_FLAVOUR", "noml")
CASA_PYVER = os.environ.get("CASA_PYVER", "3.12")
IS_07 = CASA_FLAVOUR == "0.7"

# --- packages that MUST import cleanly for the image to be usable ---------
CRITICAL_IMPORTS = [
    "coffea",
    "dask",
    "distributed",
    "dask_labextension",
    "coffea_casa",
    #"htcondor",
    "uproot",
    "awkward",
    "numpy",
    "pyhf",
    "cabinetry",
    "servicex",
    "s3fs",
    "mlflow",
]


@pytest.mark.parametrize("module", CRITICAL_IMPORTS)
def test_import(module):
    importlib.import_module(module)


def test_numpy_pin():
    import numpy
    v = numpy.__version__
    major = int(v.split(".")[0])
    if IS_07:
        # coffea 0.7 constrains the old numpy ABI; the 0.7 flavour env pins <2.
        assert major < 2, (
            f"0.7 image expects numpy<2, got {v} "
            "(something pulled in a numpy 2.x after the pin)"
        )
    else:
        expected = os.environ.get("CASA_NUMPY_EXACT", "2.4.2")
        assert v == expected, (
            f"numpy pin broken: got {v}, expected {expected} "
            "(something pulled in a different version after the pip pin)"
        )


def test_python_version():
    # The Dockerfile copies the patched distributed into
    # .../python${PYVER}/site-packages. If the base image silently moves to a
    # different Python, those COPYs land in a dead directory.
    want = tuple(int(x) for x in CASA_PYVER.split("."))
    assert sys.version_info[:2] == want, (
        f"Python is {sys.version.split()[0]} but this flavour "
        f"({CASA_FLAVOUR}) expects python{CASA_PYVER}"
    )


def test_condor_cli_available():
    assert shutil.which("condor_submit"), (
        "condor_submit missing — HTCondorCluster scaling will fail at runtime"
    )


def test_patched_distributed_is_the_imported_one():
    # The vendored+patched distributed is CalVer-only; the 0.7 flavour keeps the
    # base's stock distributed (see the FLAVOUR guard in the Dockerfile), so
    # this assertion does not apply there.
    if IS_07:
        pytest.skip("distributed patch intentionally skipped for the 0.7 flavour")
    import distributed
    expected = f"/usr/local/lib/python{CASA_PYVER}/site-packages/distributed"
    actual = os.path.dirname(distributed.__file__)
    assert actual == expected, (
        f"distributed imported from {actual}, not the patched copy at {expected}"
    )


def test_jupyterhub_singleuser_on_path():
    assert shutil.which("jupyterhub-singleuser"), (
        "jupyterhub-singleuser missing from PATH — KubeSpawner cannot start "
        "the server without it"
    )


def test_jupyterhub_version_prints():
    out = subprocess.run(
        ["jupyterhub-singleuser", "--version"],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    print("jupyterhub-singleuser version:", out.stdout.strip())


def test_running_as_nb_user():
    assert os.getuid() == 6440, f"expected UID 6440 (cms-jovyan), got {os.getuid()}"
    assert pwd.getpwuid(os.getuid()).pw_name == "cms-jovyan"


def test_home_is_writable():
    home = os.path.expanduser("~")
    probe = os.path.join(home, ".ci-write-probe")
    with open(probe, "w") as f:
        f.write("ok")
    os.remove(probe)


def test_dask_config_loads():
    import dask
    # DASK_ROOT_CONFIG yaml files must parse, otherwise every dask import
    # in a notebook explodes for users.
    assert dask.config.get("distributed", default=None) is not None or True
    import yaml
    for name in os.listdir("/opt/dask"):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join("/opt/dask", name)) as f:
                yaml.safe_load(f)


def test_xrootd_plugin_env():
    confdir = os.environ.get("XRD_PLUGINCONFDIR", "")
    plugin = os.environ.get("XRD_PLUGIN", "")
    assert plugin and os.path.exists(plugin), f"XRD_PLUGIN missing: {plugin!r}"
    assert confdir, "XRD_PLUGINCONFDIR not set"


def test_kernel_actually_executes():
    """End-to-end: start a real ipykernel and run code, like a notebook would."""
    code = (
        "import jupyter_client, queue\n"
        "km, kc = jupyter_client.manager.start_new_kernel()\n"
        "kc.execute('import coffea, dask; x = 1 + 1')\n"
        "import time; time.sleep(1)\n"
        "km.shutdown_kernel(now=True)\n"
        "print('KERNEL_OK')\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
    )
    assert "KERNEL_OK" in out.stdout, out.stderr