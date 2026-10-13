Coffea-casa — An Analysis Facility for the Columnar Object Framework For Effective Analysis
=========================================================

[![CI/CD][actions-badge]][actions-link]
[![Docker images][docker-badge]][docker-link]
[![Documentation Status][rtd-badge]][rtd-link]
[![Code style: black][black-badge]][black-link]
[![PyPI version][pypi-version]][pypi-link]
[![PyPI platforms][pypi-platforms]][pypi-link]
[![GitHub Discussion][github-discussions-badge]][github-discussions-link]
![GitHub issues](https://img.shields.io/github/issues/coffeateam/coffea-casa)
![GitHub pull requests](https://img.shields.io/github/issues-pr/coffeateam/coffea-casa)

[actions-badge]:            https://github.com/CoffeaTeam/coffea-casa/actions/workflows/pypi-ci.yml/badge.svg
[actions-link]:             https://github.com/CoffeaTeam/coffea-casa/actions
[docker-badge]:             https://github.com/CoffeaTeam/coffea-casa/actions/workflows/docker-build-test-publish.yaml/badge.svg
[docker-link]:              https://github.com/CoffeaTeam/coffea-casa/actions/workflows/docker-build-test-publish.yaml
[black-badge]:              https://img.shields.io/badge/code%20style-black-000000.svg
[black-link]:               https://github.com/psf/black
[github-discussions-badge]: https://img.shields.io/static/v1?label=Discussions&message=Ask&color=blue&logo=github
[github-discussions-link]:  https://github.com/CoffeaTeam/coffea-casa/discussions
[pypi-link]:                https://pypi.org/project/coffea-casa/
[pypi-platforms]:           https://img.shields.io/pypi/pyversions/coffea-casa
[pypi-version]:             https://badge.fury.io/py/coffea-casa.svg
[rtd-badge]:                https://readthedocs.org/projects/coffea-casa/badge/?version=latest
[rtd-link]:                 https://coffea-casa.readthedocs.io/en/latest/?badge=latest

About Coffea-casa
-----------------

Coffea-casa is an analysis facility (AF) that provides services for "low latency columnar analysis", enabling rapid processing of HEP data in a column-wise fashion with [coffea](https://coffea-hep.readthedocs.io). Its services, based on Dask and Jupyter, aim to dramatically lower time to insight and provide an easily scalable, user-friendly computational environment.

The facility runs on Kubernetes (JupyterHub via [Zero to JupyterHub](https://z2jh.jupyter.org)) and scales Dask workers out onto dedicated resources and onto resources allocated via fair share through HTCondor (e.g. the Nebraska Tier-2). It also handles single sign-on, token-based authentication and authorization for data access (XRootD / XCache), and ships a curated software stack for analysis.

Production instances:

- **[coffea.casa](https://coffea.casa)** — CMS AF at UNL (CMS AuthZ / IAM tokens)
- **[coffea-opendata.casa](https://coffea-opendata.casa)** — open-data instance
- **[coffea.af.uchicago.edu](https://coffea.af.uchicago.edu)** — ATLAS AF at UChicago

User documentation: **https://coffea-casa.readthedocs.io**. Examples live in [`docs/gallery`](https://github.com/CoffeaTeam/coffea-casa/tree/master/docs/gallery) and in [coffea-casa-tutorials](https://github.com/CoffeaTeam/coffea-casa-tutorials).


What's in this repository
-----------------

| Path | Contents |
|------|----------|
| [`coffea_casa/`](https://github.com/CoffeaTeam/coffea-casa/tree/master/coffea_casa) | `coffea_casa` Python package (`CoffeaCasaCluster`, a dask-jobqueue HTCondor cluster for the AF), published to PyPI |
| [`docker/`](https://github.com/CoffeaTeam/coffea-casa/tree/master/docker) | Dockerfiles and environment files for the notebook/scheduler and worker images ([details](https://github.com/CoffeaTeam/coffea-casa/blob/master/docker/README.md)) |
| [`charts/coffea-casa/`](https://github.com/CoffeaTeam/coffea-casa/tree/master/charts/coffea-casa) | Helm chart (JupyterHub + coffea-casa configuration) |
| [`docs/`](https://github.com/CoffeaTeam/coffea-casa/tree/master/docs) | Sphinx documentation (ReadTheDocs) and the example notebook gallery |
| `ci/`, `tests/`, `tests-charts/` | Image structure tests, spawn/smoke tests, chart tests |


The `coffea_casa` Python package
-----------------

```bash
pip install coffea-casa
```

Inside a coffea-casa notebook, the Dask JupyterLab extension starts a `CoffeaCasaCluster` for you. To create one manually:

```python
from coffea_casa import CoffeaCasaCluster
from dask.distributed import Client

cluster = CoffeaCasaCluster()  # no workers are submitted until you scale
cluster.adapt(minimum=0, maximum=20)
client = Client(cluster)
```

See the [API docs](https://coffea-casa.readthedocs.io/en/latest/cc_api.html) for all options.


Docker images
-----------------

Images are published to the OSG Harbor registry under [`hub.opensciencegrid.org/coffea-casa`](https://hub.opensciencegrid.org/harbor/projects). They are built on top of the [coffea base images](https://github.com/CoffeaTeam/af-images) (`coffeateam/coffea-*-almalinux9`):

| Image | Role |
|-------|------|
| `cc-dask-alma9` | Single-user notebook / Dask scheduler image (JupyterLab, Dask labextension, code-server, …) |
| `cc-analysis-alma9` | Slim Dask worker image |
| `cc-dask-combine-alma9` | `cc-dask-alma9` + ROOT and CMS Combine |
| `cc-analysis-combine-alma9` | `cc-analysis-alma9` + ROOT and CMS Combine |

`cc-dask-alma9` and `cc-analysis-alma9` are built for several coffea **flavours**:

| Flavour | Base image | Python |
|---------|------------|--------|
| `noml` (default) | `coffeateam/coffea-almalinux9-noml` | 3.12 |
| `dak` | `coffeateam/coffea-dak-almalinux9` (coffea with dask-awkward) | 3.12 |
| `full` | `coffeateam/coffea-almalinux9` | 3.12 |
| `0.7` | `coffeateam/coffea-0.7-almalinux9` (legacy coffea 0.7.x) | 3.11 |

Tags have the form `<version>-<flavour>` (e.g. `cc-dask-alma9:2026.10.12-dak`); the default `noml` flavour is also published under the bare `<version>` tag. Base image versions are bumped automatically by a daily workflow that opens a PR.

See [`docker/README.md`](https://github.com/CoffeaTeam/coffea-casa/blob/master/docker/README.md) for build arguments and how to build images locally.


Helm chart
-----------------

```bash
helm repo add coffea-casa https://coffeateam.github.io/coffea-casa
helm repo update
helm search repo coffea-casa
```

See the [chart README](https://github.com/CoffeaTeam/coffea-casa/blob/master/charts/coffea-casa/README.md), the [deployment guide](https://coffea-casa.readthedocs.io/en/latest/cc_deployment.html) and the [local (k3d / minikube) deployment guide](https://coffea-casa.readthedocs.io/en/latest/cc_local_deployment.html).


Versioning and releases
-----------------

Coffea-casa uses [calendar versioning](https://calver.org/) (`YYYY.MM.DD`, with a `.N` suffix for further releases on the same day). Releasing is automated with GitHub Actions — there are no version numbers to bump by hand:

1. **Every push to `master`** is automatically tagged with the next CalVer tag.
   - Images whose sources changed are published as `:development` / `:development-<flavour>`.
   - The Helm chart is published to https://coffeateam.github.io/coffea-casa if `charts/` changed. Since Helm requires SemVer, the chart version maps the tag to `YYYY.MMDD.N` (e.g. `2026.10.12` → `2026.1012.0`); `appVersion` is the exact git tag.
2. **Publishing a GitHub Release** from a tag ([releases](https://github.com/CoffeaTeam/coffea-casa/releases)):
   - builds, tests and publishes all images as `:<tag>` / `:<tag>-<flavour>`;
   - publishes the `coffea_casa` package to [PyPI](https://pypi.org/project/coffea-casa/) (version derived from the tag);
   - republishes the Helm chart.

Pull requests build and test images and the chart without publishing anything.


Analysis repositories using coffea-casa
-----------------

- [BTVNanoCommissioning](https://github.com/cms-btv-pog/BTVNanoCommissioning) — commissioning studies in the CMS BTV POG based on (custom) NanoAOD samples
- [SUEPCoffea_dask](https://github.com/SUEPPhysics/SUEPCoffea_dask) — SUEP analysis using fastjet with awkward input from PFNano NanoAOD samples
- [hgg-coffea](https://github.com/lgray/hgg-coffea) — tools for running the CMS Higgs to two photons analysis on NanoAOD


References
-----------------

* M. Adamec, G. Attebury, K. Bloom, B. Bockelman, C. Lundstedt, O. Shadura and J. Thiltges, *Coffea-casa: an analysis facility prototype*, [arXiv:2103.01871](https://arxiv.org/abs/2103.01871) (2021).
* PyHEP 2020 coffea-casa proceedings: [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4136273.svg)](https://doi.org/10.5281/zenodo.4136273)
* PyHEP 2020 introductory talk: [YouTube](https://www.youtube.com/watch?v=CDIFd1gDbSc)


Contact us
-----------------

Questions and feedback are welcome in [GitHub Discussions](https://github.com/CoffeaTeam/coffea-casa/discussions), [GitHub Issues](https://github.com/CoffeaTeam/coffea-casa/issues), or the IRIS-HEP Slack.
