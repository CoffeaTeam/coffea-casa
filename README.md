Coffea-casa - A Prototype U.S. CMS analysis facility for Columnar Object Framework For Effective Analysis
=========================================================

[![Actions Status][actions-badge]][actions-link]
[![Documentation Status][rtd-badge]][rtd-link]
[![Code style: black][black-badge]][black-link]
[![PyPI version][pypi-version]][pypi-link]
[![PyPI platforms][pypi-platforms]][pypi-link]
[![GitHub Discussion][github-discussions-badge]][github-discussions-link]
![GitHub issues](https://img.shields.io/github/issues/coffeateam/coffea-casa)
![GitHub pull requests](https://img.shields.io/github/issues-pr/coffeateam/coffea-casa)

[actions-badge]:            https://github.com/CoffeaTeam/coffea-casa/workflows/CI/CD/badge.svg
[actions-link]:             https://github.com/CoffeaTeam/coffea-casa/actions
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

The prototype analysis facility provides services for “low latency columnar analysis”, enabling rapid processing of data in a column-wise fashion. These services, based on Dask and Jupyter notebooks, aim to dramatically lower time for analysis and provide an easily-scalable and user-friendly computational environment that will simplify, facilitate, and accelerate the delivery of HEP results. The facility is built on top of a Kubernetes cluster and integrates dedicated resources with resources allocated via fairshare through the local HTCondor system. In addition to the user-facing interfaces such as Dask, the facility also manages access control through single-sign-on and authentication & authorization for data access. The notebooks in this repository and ![Coffea-casa tutorials](https://github.com/CoffeaTeam/coffea-casa-tutorials) include simple HEP analysis examples, managed interactively in a Jupyter notebook and scheduled on Dask workers and accessing both public and protected data.


Check analysis repositories using coffea-casa
-----------------

- ![Commissioning studies in the BTV POG based on (custom) nanoAOD samples](https://github.com/cms-btv-pog/BTVNanoCommissioning#coffea-casa-nebraska-af)


Docker images used for Coffea-casa
============

Latest ![DockerHub Images](https://hub.docker.com/orgs/coffeateam/repositories):

| Image           | Description                                   |  Size | Pulls | Version | Layers |
|-----------------|-----------------------------------------------|--------------|-------------|-------------|-------------|
| coffea-casa     | Dask scheduler image for coffea-casa hub            | ![](https://img.shields.io/docker/image-size/coffeateam/coffea-casa?sort=date) | ![](https://img.shields.io/docker/pulls/coffeateam/coffea-casa?sort=date) | ![](https://img.shields.io/docker/v/coffeateam/coffea-casa?sort=date) | ![](https://img.shields.io/microbadger/layers/coffeateam/coffea-casa)
| coffea-casa-analysis | Dask worker image for coffea-casa hub    | ![](https://img.shields.io/docker/image-size/coffeateam/coffea-casa-analysis?sort=date) | ![](https://img.shields.io/docker/pulls/coffeateam/coffea-casa-analysis?sort=date) | ![](https://img.shields.io/docker/v/coffeateam/coffea-casa-analysis?sort=date) | ![](https://img.shields.io/microbadger/layers/coffeateam/coffea-casa-analysis)


Image tagging and "continuous building"
-----------------

This repository uses GitHub Actions to build images, run tests, and push images to DockerHub (Docker image tags are syncronised with Coffea-casa releases).

1. Tags pushed to GitHub represent "production" releases with corresponding tags on dockerhub `coffeateam/coffea-casa:x.x.x` and `coffeateam/coffea-casa-analysis:x.x.x`. The latest tag also corresponds to the most recent GitHub tag.

Please note we are using ![date-based versioning](https://calver.org/) for Coffea-casa Docker images and Pypi module.


References
============

* Coffea-casa: an analysis facility prototype, M. Adamec, G. Attebury, K. Bloom, B. Bockelman, C. Lundstedt, O. Shadura and J. Thiltges, arXiv ![2103.01871](https://arxiv.org/abs/2103.01871) (02 Mar 2021).
* PyHEP 2020 coffea-casa proceedings: [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4136273.svg)](https://doi.org/10.5281/zenodo.4136273)
* The PyHEP 2020 introductory Youtube video is [here](https://www.youtube.com/watch?v=CDIFd1gDbSc).


Contact us
============

Interested? You can reach us in ![Github Discussions](https://github.com/CoffeaTeam/coffea-casa/discussions) or in IRIS-HEP Slack channel.

