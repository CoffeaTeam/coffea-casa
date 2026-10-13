# AGENTS.md

Instructions for AI coding agents working in this repository. Humans: see
[README.md](README.md) and the docs at https://coffea-casa.readthedocs.io.

Subdirectories have their own `AGENTS.md` with more detail; the file closest to
the code you edit takes precedence:

- [`charts/coffea-casa/AGENTS.md`](charts/coffea-casa/AGENTS.md) – Helm chart
- [`docker/AGENTS.md`](docker/AGENTS.md) – container images

## Project overview

Coffea-casa is an analysis facility for HEP columnar analysis: JupyterHub
(Zero to JupyterHub) + Dask on Kubernetes, with Dask workers bursting to
HTCondor, token-based data access (XRootD / XCache), and a curated software
stack. Production instances: coffea.casa (CMS @ UNL), coffea-opendata.casa,
coffea.af.uchicago.edu (ATLAS).

This repository holds several independently built components:

| Path | What | Built/tested by |
| --- | --- | --- |
| `coffea_casa/` | Python package `coffea-casa` (PyPI): Dask cluster wrappers (`CoffeaCasaCluster`), jobqueue config, plugins | `pypi-ci.yml` |
| `docker/` | AlmaLinux 9 images (`cc-dask-alma9`, `cc-analysis-alma9`, `histserv`) | `docker-build-test-publish.yaml` |
| `charts/coffea-casa/` | Helm chart wrapping the z2jh `jupyterhub` chart | `chart-test.yaml` |
| `ci/` | values overlays, structure tests and spawn-test scripts used by CI | – |
| `tests/` | package unit tests, in-image smoke tests, bats tests | see below |
| `tests-charts/` | pytest tests against a deployed hub | – |
| `docs/` | Sphinx docs (reStructuredText, Read the Docs) | `.readthedocs.yml` |
| `tools/` | helper scripts (e.g. JSON schema generation for the chart) | – |
| `coffea-casa-tutorials/` | **git submodule** – do not edit here; change it upstream | – |

When a task touches more than one component, say so explicitly in the PR.

## Setup

```sh
git submodule update --init      # only if you need the tutorials
python -m pip install -e ".[dev]"
pre-commit install               # optional, see "Code style"
```

Python >= 3.8 is supported (CI matrix in `pypi-ci.yml`); don't use syntax or
stdlib APIs newer than 3.8 in `coffea_casa/`.

## Build & test commands (Python package)

Mirror what CI runs:

```sh
flake8 --ignore=E501,E303,E301,W503,W292 coffea_casa   # lint (pypi-ci.yml)
pytest                                                 # unit tests
bats tests/worker-args.bats                            # worker arg parsing (test-prepare-workers.yml)
python -m build                                        # sdist + wheel (hatchling)
```

Notes:

- `tests/test_image_smoke.py` and `tests/test_analysis_smoke.py` run **inside
  built images**, not on the host. They skip/fail on a laptop by design. See
  their module docstrings and `docker/AGENTS.md` for the `docker run` command.
- `tests-charts/` needs a running hub; it is not part of the default `pytest` run.
- Add or update tests in `tests/` for any change to `coffea_casa/`.

## Code style

- Formatter: black `23.10.1` (pinned via `required-version`), line length 88.
- flake8 config is in `pyproject.toml`; CI uses the narrower ignore list above.
- `pre-commit run --all-files` runs the full hook set (isort, pyupgrade,
  codespell, mypy, …). Known issue: both `double-quote-string-fixer` and
  `black` are enabled and disagree on quote style. Don't "fix" quotes across
  unrelated files; keep the style of the file you are editing and keep diffs
  focused.
- Versioning is from git tags via hatch-vcs. **Never edit or commit
  `coffea_casa/_version.py`** and never hard-code a version number.

## Docs

- Sphinx sources are `docs/*.rst`. Build locally with
  `pip install -e ".[docs]" && make -C docs html`.
- User-facing behaviour changes (new config keys, cluster options, image
  flavours) need a docs update in the same PR.

## Security considerations

- Never commit credentials: tokens, IAM / CMS AuthZ client secrets, X.509
  proxies, kubeconfigs, or private keys. `docker/certs/` contains **public**
  CA certificates only.
- `charts/coffea-casa/values-prod.yaml` and `values-cmsaf-prod.yaml` describe
  live production deployments. Don't modify them unless the task explicitly
  asks for it.
- Be conservative with anything touching authentication (JupyterHub
  authenticators, token exchange, XCache auth) – flag such changes in the PR.

## PR / commit guidelines

- Default branch is `master`.
- Small, focused PRs; title prefix the component when useful, e.g.
  `chart: …`, `docker: …`, `coffea_casa: …`, `docs: …`.
- CI must pass: package lint/tests, and for `charts/**` or `docker/**`
  changes, the chart and image workflows (they are path-filtered).
- Don't bump pinned base images, the z2jh dependency version, or package pins
  as a drive-by; do it in a dedicated PR.
