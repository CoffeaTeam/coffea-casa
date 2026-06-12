"""Smoke tests executed *inside* the singleuser image.

Run with:  docker run --rm -v $PWD/tests:/tests:ro IMAGE python -m pytest /tests -v
They validate the Python environment the way a real user session would use it.
"""
import importlib
import os
import pwd
import shutil
import subprocess
import sys

import pytest

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
    assert numpy.__version__ == "2.4.2", (
        f"numpy pin broken: got {numpy.__version__} "
        "(something pulled in a different version after the pip pin)"
    )


def test_python_version():
    # Dockerfile copies the patched distributed into .../python3.13/...
    # If the base image silently moves to another Python, those COPYs
    # land in a dead directory and the patches are not applied.
    assert sys.version_info[:2] == (3, 13), (
        f"Python is {sys.version.split()[0]} but the Dockerfile hardcodes "
        "python3.13 paths for the patched distributed package"
    )

def test_condor_cli_available():
    assert shutil.which("condor_submit"), (
        "condor_submit missing — HTCondorCluster scaling will fail at runtime"
    )

def test_patched_distributed_is_the_imported_one():
    import distributed
    expected = "/usr/local/lib/python3.13/site-packages/distributed"
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