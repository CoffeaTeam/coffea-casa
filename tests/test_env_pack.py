import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from coffea_casa import env_pack
from coffea_casa.coffea_casa import CoffeaCasaCluster
from coffea_casa.env_pack import ShippedEnv


def make_env(path):
    (path / "conda-meta").mkdir(parents=True)
    return path


# ===== should_ship_env =====

def test_auto_skips_base_env(tmp_path, monkeypatch):
    base = make_env(tmp_path / "base")
    monkeypatch.setenv("CONDA_DIR", str(base))
    assert env_pack.should_ship_env("auto", prefix=base) is False


def test_auto_ships_named_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CONDA_DIR", str(make_env(tmp_path / "base")))
    assert env_pack.should_ship_env("auto", prefix=make_env(tmp_path / "foo")) is True


def test_auto_skips_non_conda_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CONDA_DIR", str(make_env(tmp_path / "base")))
    venv = tmp_path / "venv"
    venv.mkdir()
    assert env_pack.should_ship_env("auto", prefix=venv) is False


def test_forced_non_conda_env_raises(tmp_path):
    venv = tmp_path / "venv"
    venv.mkdir()
    with pytest.raises(RuntimeError, match="not a conda environment"):
        env_pack.should_ship_env(True, prefix=venv)


def test_disabled(tmp_path):
    assert env_pack.should_ship_env(False, prefix=make_env(tmp_path / "foo")) is False


# ===== find_editable_packages =====

def write_dist(site, name, direct_url=None):
    info = site / f"{name}-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n")
    if direct_url is not None:
        (info / "direct_url.json").write_text(json.dumps(direct_url))


def test_find_editable_packages(tmp_path):
    site = tmp_path / "site-packages"
    proj = tmp_path / "myana"
    (proj / "src" / "myana").mkdir(parents=True)
    (proj / "pyproject.toml").write_text("")
    write_dist(site, "myana", {"url": proj.as_uri(), "dir_info": {"editable": True}})
    write_dist(site, "regular")
    write_dist(site, "fromdir", {"url": proj.as_uri(), "dir_info": {}})
    # Legacy setup.py develop: egg-link points at the src dir, root is above it
    legacy = tmp_path / "legacy"
    (legacy / "src").mkdir(parents=True)
    (legacy / "setup.py").write_text("")
    (site / "legacy.egg-link").write_text(f"{legacy / 'src'}\n.\n")

    found = env_pack.find_editable_packages(site)
    assert found == {"myana": proj.resolve(), "legacy": legacy.resolve()}


# ===== pack_env caching =====

def test_pack_env_reuses_cache_until_env_changes(tmp_path, monkeypatch):
    prefix = make_env(tmp_path / "foo")
    (prefix / "conda-meta" / "numpy-2.0-0.json").write_text("{}")
    packed = []

    def fake_pack(prefix, output, **kwargs):
        assert kwargs["ignore_editable_packages"] is True
        packed.append(output)
        Path(output).write_bytes(b"tarball")

    monkeypatch.setitem(sys.modules, "conda_pack",
                        type("M", (), {"pack": staticmethod(fake_pack)}))
    cache = tmp_path / "cache"
    first = env_pack.pack_env(prefix, cache)
    assert env_pack.pack_env(prefix, cache) == first
    assert len(packed) == 1

    (prefix / "conda-meta" / "scipy-1.0-0.json").write_text("{}")
    second = env_pack.pack_env(prefix, cache)
    assert second != first and len(packed) == 2
    # The stale pack of this env is removed
    assert sorted(cache.glob("cc-env-foo-*.tar.gz")) == [second]


def test_pack_env_without_conda_pack(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "conda_pack", None)
    with pytest.raises(RuntimeError, match="conda-pack is needed"):
        env_pack.pack_env(make_env(tmp_path / "foo"), tmp_path / "cache")


# ===== cluster integration =====

def directives_for(shipped):
    with patch("coffea_casa.coffea_casa.prepare_shipped_env", return_value=shipped) as prep:
        job_kwargs = CoffeaCasaCluster._modify_job_kwargs({}, force_tcp=True, ship_env="auto")
    prep.assert_called_once_with("auto")
    return job_kwargs["job_extra_directives"]


def test_shipped_env_is_transferred_not_encrypted(tmp_path, monkeypatch):
    env_yaml = tmp_path / "environment.yaml"
    env_yaml.write_text("dependencies: []")
    monkeypatch.setattr("coffea_casa.coffea_casa.CONDA_ENV", env_yaml)
    tarball = tmp_path / "cc-env-foo-abc.tar.gz"
    wheels = tmp_path / "wheels-x" / env_pack.WHEELS_DIR_NAME

    directives = directives_for(ShippedEnv(tarball, wheels))
    transfer = directives["transfer_input_files"]
    assert str(tarball) in transfer and str(wheels) in transfer
    assert str(tarball) not in directives["encrypt_input_files"]
    assert directives["+CoffeaCasaEnvTarball"] == '"cc-env-foo-abc.tar.gz"'
    # The base-env update files don't apply when the env is shipped
    assert str(env_yaml) not in transfer


def test_no_shipped_env_keeps_environment_yaml(tmp_path, monkeypatch):
    env_yaml = tmp_path / "environment.yaml"
    env_yaml.write_text("dependencies: []")
    monkeypatch.setattr("coffea_casa.coffea_casa.CONDA_ENV", env_yaml)

    directives = directives_for(None)
    assert str(env_yaml) in directives["transfer_input_files"]
    assert "+CoffeaCasaEnvTarball" not in directives


# ===== original env path on the workers =====

def test_shipped_env_sets_worker_preload_and_original_prefix(tmp_path):
    shipped = ShippedEnv(tmp_path / "cc-env-foo-abc.tar.gz", prefix="/home/u/.conda/envs/foo")
    env = directives_for(shipped)["environment"]
    assert "COFFEA_CASA_ENV_PREFIX=/home/u/.conda/envs/foo" in env
    assert "DASK_DISTRIBUTED__WORKER__PRELOAD=coffea_casa.ship_env_preload" in env


def test_no_shipped_env_sets_no_environment():
    assert "environment" not in directives_for(None)


def test_prepare_shipped_env_records_the_notebook_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(env_pack, "should_ship_env", lambda mode: True)
    monkeypatch.setattr(env_pack, "pack_env", lambda cache_dir: tmp_path / "t.tar.gz")
    monkeypatch.setattr(env_pack, "find_editable_packages", lambda: {})
    assert env_pack.prepare_shipped_env("auto").prefix == Path(sys.prefix)


def test_preload_links_original_prefix(tmp_path):
    from coffea_casa.ship_env_preload import link_original_prefix
    actual = make_env(tmp_path / "scratch" / "cc-env")
    original = tmp_path / "home" / ".conda" / "envs" / "foo"
    assert link_original_prefix(original, actual) == "linked"
    assert original.is_symlink() and original.resolve() == actual.resolve()
    assert link_original_prefix(original, actual) == "same"


def test_preload_leaves_an_existing_path_alone(tmp_path):
    from coffea_casa.ship_env_preload import link_original_prefix
    actual = make_env(tmp_path / "cc-env")
    original = make_env(tmp_path / "other-env")
    assert link_original_prefix(original, actual) == "exists"
    assert not original.is_symlink()


def test_preload_does_not_raise_when_it_cannot_link(tmp_path):
    from coffea_casa.ship_env_preload import link_original_prefix
    actual = make_env(tmp_path / "cc-env")
    readonly = tmp_path / "ro"
    readonly.mkdir()
    readonly.chmod(0o500)
    try:
        assert link_original_prefix(readonly / "envs" / "foo", actual) == "failed"
    finally:
        readonly.chmod(0o700)
