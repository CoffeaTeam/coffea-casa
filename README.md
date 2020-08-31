coffea-casa - A Prototype U.S. CMS analysis facility for Columnar Object Framework For Effective Analysis
=========================================================

![CI/CD status](https://github.com/coffeateam/coffea-casa/workflows/CI/CD/badge.svg)
![GitHub issues](https://img.shields.io/github/issues/coffeateam/coffea-casa)
![GitHub pull requests](https://img.shields.io/github/issues-pr/coffeateam/coffea-casa)
[![Documentation Status](https://readthedocs.org/projects/coffea-casa/badge/?version=latest)](https://coffea-casa.readthedocs.io/en/latest/?badge=latest)

Latest DockerHub Images: https://hub.docker.com/orgs/coffeateam/repositories

| Image           | Description                                   |  Size | Pulls | Version | Layers |
|-----------------|-----------------------------------------------|--------------|-------------|-------------|-------------|
| coffea-casa     | Dask scheduler image for coffea-casa hub            | ![](https://img.shields.io/docker/image-size/coffeateam/coffea-casa?sort=date) | ![](https://img.shields.io/docker/pulls/coffeateam/coffea-casa?sort=date) | ![](https://img.shields.io/docker/v/coffeateam/coffea-casa?sort=date) | ![](https://img.shields.io/microbadger/layers/coffeateam/coffea-casa)
| coffea-casa-analysis | Dask worker image for coffea-casa hub    | ![](https://img.shields.io/docker/image-size/coffeateam/coffea-casa-analysis?sort=date) | ![](https://img.shields.io/docker/pulls/coffeateam/coffea-casa-analysis?sort=date) | ![](https://img.shields.io/docker/v/coffeateam/coffea-casa-analysis?sort=date) | ![](https://img.shields.io/microbadger/layers/coffeateam/coffea-casa-analysis)


About
============

The prototype analysis facility provides services for “low latency columnar analysis”, enabling rapid processing of data in a column-wise fashion. These services, based on Dask and Jupyter notebooks, aim to dramatically lower time for analysis and provide an easily-scalable and user-friendly computational environment that will simplify, facilitate, and accelerate the delivery of HEP results. The facility is built on top of a Kubernetes cluster and integrates dedicated resources with resources allocated via fairshare through the local HTCondor system. In addition to the user-facing interfaces such as Dask, the facility also manages access control through single-sign-on and authentication & authorization for data access. The notebooks in this repository and ![Coffea-casa tutorials](https://github.com/CoffeaTeam/coffea-casa-tutorials) include simple HEP analysis examples, managed interactively in a Jupyter notebook and scheduled on Dask workers and accessing both public and protected data.


Image tagging and "continuous building"
============

This repository uses GitHub Actions to build images, run tests, and push images to DockerHub.

1. Tags pushed to GitHub represent "production" releases with corresponding tags on dockerhub `coffeateam/coffea-casa:x.x.x` and `coffeateam/coffea-casa-analysis:x.x.x`. The latest tag also corresponds to the most recent GitHub tag.


References
============
The PyHEP introductory Youtube video is [here](https://www.youtube.com/watch?v=CDIFd1gDbSc).
