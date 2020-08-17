coffea-casa - A Prototype U.S. CMS analysis facility for Columnar Object Framework For Effective Analysis
=========================================================

![CI/CD status](https://github.com/coffeateam/coffea-casa/workflows/CI/CD/badge.svg)
![GitHub issues](https://img.shields.io/github/issues/coffeateam/coffea-casa)
![GitHub pull requests](https://img.shields.io/github/issues-pr/coffeateam/coffea-casa)

The prototype analysis facility provides services for “low latency columnar analysis”, enabling rapid processing of data in a column-wise fashion. These services, based on Dask and Jupyter notebooks, aim to dramatically lower time for analysis and provide an easily-scalable and user-friendly computational environment that will simplify, facilitate, and accelerate the delivery of HEP results. The facility is built on top of a local Kubernetes cluster and integrates dedicated resources with resources allocated via fairshare through the local HTCondor system. In addition to the user-facing interfaces such as Dask, the facility also manages access control through single-sign-on and authentication & authorization for data access. The notebooks include simple HEP analysis examples, managed interactively in a Jupyter notebook and scheduled on Dask workers and accessing both public and protected data.

Docker images
============
## coffea-casa

Dask scheduler image used in CMSAF:
[![](https://images.microbadger.com/badges/image/coffeateam/coffea-casa.svg)](https://microbadger.com/images/coffeateam/coffea-casa)
[![](https://images.microbadger.com/badges/version/coffeateam/coffea-casa.svg)](https://microbadger.com/images/coffeateam/coffea-casa)

## coffea-casa-analysis

Dask worker image used in CMSAF:
[![](https://images.microbadger.com/badges/image/coffeateam/coffea-casa-analysis.svg)](https://microbadger.com/images/coffeateam/coffea-casa-analysis )
[![](https://images.microbadger.com/badges/version/coffeateam/coffea-casa-analysis.svg)](https://microbadger.com/images/coffeateam/coffea-casa-analysis)

References
============
The PyHEP introductory Youtube video is [here](https://www.youtube.com/watch?v=CDIFd1gDbSc).
