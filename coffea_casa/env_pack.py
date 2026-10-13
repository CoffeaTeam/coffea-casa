"""Ship the notebook's active conda environment to HTCondor workers.

The Dask scheduler runs inside the notebook kernel, so workers must run the
same environment as the kernel (matching dask/distributed and analysis code).
When the kernel is not running in the image's base env, the env is packed with
conda-pack, the tarball is transferred with the job, and the worker entrypoint
unpacks it and starts dask-worker with that env's python.

conda-pack cannot pack editable (``pip install -e``) packages. Those are
skipped by conda-pack and instead built into wheels that are shipped next to
the tarball and installed on the worker after unpacking.
"""
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

# Names the worker entrypoint (worker-args.sh) relies on
ENV_TARBALL_ATTR = "CoffeaCasaEnvTarball"
WHEELS_DIR_NAME = "cc-editable-wheels"

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "coffea-casa" / "envs"
# Per-cluster wheel directories older than this are pruned on the next pack
WHEELS_MAX_AGE = 7 * 24 * 3600


class ShippedEnv:
    """Files to transfer so workers run the notebook's environment."""

    def __init__(self, tarball, wheels_dir=None):
        self.tarball = Path(tarball)
        self.wheels_dir = Path(wheels_dir) if wheels_dir else None

    @property
    def input_files(self):
        files = [self.tarball]
        if self.wheels_dir:
            files.append(self.wheels_dir)
        return files


def base_env_prefix():
    """Prefix of the image's base conda env (CONDA_DIR, /usr/local in the image)."""
    if os.environ.get("CONDA_DIR"):
        return Path(os.environ["CONDA_DIR"]).resolve()
    if os.environ.get("CONDA_EXE"):
        return Path(os.environ["CONDA_EXE"]).resolve().parents[1]
    return Path("/usr/local").resolve()


def active_env_prefix():
    return Path(sys.prefix).resolve()


def is_conda_env(prefix):
    return (Path(prefix) / "conda-meta").is_dir()


def should_ship_env(mode="auto", prefix=None):
    """Decide whether to ship the env at ``prefix`` (default: the kernel's).

    ``mode`` is "auto" (ship only a non-base conda env), True or False.
    """
    if mode is False or mode is None:
        return False
    prefix = Path(prefix or active_env_prefix()).resolve()
    if not is_conda_env(prefix):
        if mode is True:
            raise RuntimeError(
                f"ship_env=True but {prefix} is not a conda environment; "
                "only conda environments can be shipped to workers.")
        return False
    if mode == "auto":
        return prefix != base_env_prefix()
    return True


def _project_root(path):
    """Walk up from ``path`` to the directory holding pyproject.toml/setup.py."""
    path = Path(path).resolve()
    for candidate in (path, *path.parents):
        if (candidate / "pyproject.toml").is_file() or (candidate / "setup.py").is_file():
            return candidate
    return None


def find_editable_packages(site_packages=None):
    """Return {distribution name: project source dir} for editable installs."""
    site_packages = Path(site_packages or sysconfig.get_paths()["purelib"])
    editables = {}
    for dist in importlib.metadata.distributions(path=[str(site_packages)]):
        raw = dist.read_text("direct_url.json")
        if not raw:
            continue
        try:
            info = json.loads(raw)
        except ValueError:
            continue
        if not info.get("dir_info", {}).get("editable"):
            continue
        url = urlparse(info.get("url", ""))
        if url.scheme != "file":
            continue
        root = _project_root(unquote(url.path))
        if root:
            editables[dist.metadata["Name"]] = root
    # Legacy `setup.py develop` installs leave an .egg-link instead
    for link in site_packages.glob("*.egg-link"):
        lines = link.read_text().splitlines()
        root = _project_root(lines[0].strip()) if lines else None
        if root:
            editables.setdefault(link.stem, root)
    return editables


def env_fingerprint(prefix):
    """Hash identifying the installed contents of the env at ``prefix``.

    Changes whenever a conda or pip package is installed, removed or
    reinstalled, so a cached tarball is only reused for an unchanged env.
    """
    prefix = Path(prefix)
    h = hashlib.sha256(str(prefix).encode())
    entries = sorted((prefix / "conda-meta").glob("*.json"))
    site_packages = Path(sysconfig.get_paths(vars={"base": str(prefix),
                                                   "platbase": str(prefix)})["purelib"])
    if site_packages.is_dir():
        entries += sorted(site_packages.glob("*.dist-info"))
        entries += sorted(site_packages.glob("*.egg-link"))
    for entry in entries:
        h.update(f"{entry.name}:{entry.stat().st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


def pack_env(prefix=None, cache_dir=DEFAULT_CACHE_DIR):
    """Pack the env with conda-pack, reusing a cached tarball if unchanged."""
    try:
        import conda_pack
    except ImportError:
        raise RuntimeError(
            "conda-pack is needed to ship this environment to workers: "
            "`mamba install -c conda-forge conda-pack` (or pass ship_env=False)."
        ) from None
    prefix = Path(prefix or active_env_prefix()).resolve()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    stem = f"cc-env-{prefix.name}-"
    tarball = cache_dir / f"{stem}{env_fingerprint(prefix)}.tar.gz"
    if tarball.is_file():
        return tarball

    print(f"Packing conda environment {prefix} for the workers "
          "(only needed again when the environment changes)...")
    tmp = tarball.with_name(f".{tarball.name}.{uuid.uuid4().hex}.tmp")
    try:
        conda_pack.pack(prefix=str(prefix), output=str(tmp), format="tar.gz",
                        ignore_editable_packages=True, n_threads=-1)
        os.replace(tmp, tarball)
    finally:
        tmp.unlink(missing_ok=True)
    # Drop older packs of this env; they are no longer what workers should run
    for old in cache_dir.glob(f"{stem}*.tar.gz"):
        if old != tarball:
            old.unlink(missing_ok=True)
    print(f"Packed {tarball} ({tarball.stat().st_size / 2**30:.2f} GiB)")
    return tarball


def build_editable_wheels(editables, cache_dir=DEFAULT_CACHE_DIR):
    """Build a wheel for each editable project; return the wheel directory.

    Wheels go in a fresh per-cluster ``<unique>/cc-editable-wheels`` directory
    so concurrent clusters never see each other's builds. They are rebuilt for
    every cluster since editable sources change without reinstalling.
    """
    cache_dir = Path(cache_dir)
    _prune_wheel_dirs(cache_dir)
    wheels_dir = cache_dir / f"wheels-{uuid.uuid4().hex}" / WHEELS_DIR_NAME
    wheels_dir.mkdir(parents=True)
    for name, source in sorted(editables.items()):
        print(f"Building wheel for editable package {name} from {source}")
        base_cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps",
                    "--quiet", "--wheel-dir", str(wheels_dir), str(source)]
        # Build against the env's own build backend first (fast, offline); fall
        # back to an isolated build if the backend isn't installed in the env.
        result = subprocess.run(base_cmd + ["--no-build-isolation"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(base_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not build a wheel for editable package {name} ({source}), "
                "so it cannot be shipped to workers. Fix the build, install it "
                "non-editable, or pass ship_env=False.\n" + result.stderr[-2000:])
    return wheels_dir


def _prune_wheel_dirs(cache_dir):
    now = time.time()
    for old in cache_dir.glob("wheels-*"):
        try:
            if now - old.stat().st_mtime > WHEELS_MAX_AGE:
                shutil.rmtree(old, ignore_errors=True)
        except FileNotFoundError:
            pass


def prepare_shipped_env(mode="auto", cache_dir=DEFAULT_CACHE_DIR):
    """Pack the kernel's env (and editable wheels) if it should be shipped.

    Returns a ShippedEnv, or None when workers should use the image's env.
    """
    if not should_ship_env(mode):
        return None
    tarball = pack_env(cache_dir=cache_dir)
    editables = find_editable_packages()
    wheels_dir = build_editable_wheels(editables, cache_dir) if editables else None
    return ShippedEnv(tarball, wheels_dir)
