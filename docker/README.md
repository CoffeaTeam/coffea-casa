## Coffea-casa Docker images

Two images are built from **generic**, parametrized Dockerfiles:

| Dockerfile | Role | Published as |
| --- | --- | --- |
| `Dockerfile.cc-dask-alma9` | Full single-user notebook / Dask scheduler (JupyterLab, code-server, …) | `cc-dask-alma9` |
| `Dockerfile.cc-analysis-alma9` | Slim Dask worker / analysis image | `cc-analysis-alma9` |

The same two Dockerfiles produce every variant. What goes *into* an image is
decided at build time by build-args plus a set of conda/pip environment files
in [`env/`](env), not by editing the Dockerfile.

### The two axes: flavour and combine

**Flavour** selects which coffea base image the casa layer is installed on top
of. Pass the base image, its flavour label, and the base's Python minor version:

| Flavour | Base image (Docker Hub) | Python | Notes |
| --- | --- | --- | --- |
| `noml` | `coffeateam/coffea-almalinux9-noml` | 3.12 | Default / canonical. No ML stack. |
| `dak`  | `coffeateam/coffea-dak-almalinux9`  | 3.12 | CalVer coffea **with** dask-awkward. |
| `full` | `coffeateam/coffea-almalinux9`      | 3.12 | CalVer coffea, no dask-awkward. |
| `0.7`  | `coffeateam/coffea-0.7-almalinux9`  | 3.11 | Legacy coffea 0.7.x. |

**Combine** (`COMBINE=1`) overlays `root` + `cms-combine` on top of any flavour,
producing the `cc-*-combine-alma9` images. There is no separate combine
Dockerfile — it is the same file with one extra env overlay.

### Environment files

Package sets live in [`env/`](env) and are applied in order (later wins):

| File | Applied when | Contents |
| --- | --- | --- |
| `casa-common.yaml` | always | packages shared by both roles (cabinetry, pyhf, ndcctools, servicex, coffea-casa itself, …) |
| `casa-dask.yaml` | `Dockerfile.cc-dask-alma9` | Jupyter/Lab/code-server stack |
| `casa-analysis.yaml` | `Dockerfile.cc-analysis-alma9` | slim worker extras (supervisor, aiostream) |
| `casa-flavour-<FLAVOUR>.yaml` | always | version-sensitive pins (numpy, xrootd, numba) — differs per flavour |
| `casa-combine.yaml` | `COMBINE=1` | `root` + `cms-combine` |

To change a package or a pin, edit the relevant env file — not the Dockerfile.

## Building locally

**Run builds with `docker/` as the build context** (the `COPY env/ …` paths are
relative to it). From inside the `docker/` directory the context is `.`:

```bash
cd docker/

# Default (noml) dask scheduler image
docker build --platform linux/amd64 \
  --build-arg BASE_IMAGE=coffeateam/coffea-almalinux9-noml:2026.7.0-py3.12 \
  --build-arg FLAVOUR=noml \
  --build-arg PYVER=3.12 \
  -t hub.opensciencegrid.org/coffea-casa/cc-dask-alma9:latest \
  -f Dockerfile.cc-dask-alma9 .

# dak worker image
docker build --platform linux/amd64 \
  --build-arg BASE_IMAGE=coffeateam/coffea-dak-almalinux9:2026.7.0-py3.12 \
  --build-arg FLAVOUR=dak \
  --build-arg PYVER=3.12 \
  -t hub.opensciencegrid.org/coffea-casa/cc-analysis-alma9:latest-dak \
  -f Dockerfile.cc-analysis-alma9 .

# combine image (root + cms-combine) on the noml base
docker build --platform linux/amd64 \
  --build-arg BASE_IMAGE=coffeateam/coffea-almalinux9-noml:2026.7.0-py3.12 \
  --build-arg FLAVOUR=noml \
  --build-arg PYVER=3.12 \
  --build-arg COMBINE=1 \
  -t hub.opensciencegrid.org/coffea-casa/cc-dask-combine-alma9:latest \
  -f Dockerfile.cc-dask-alma9 .
```

> **`PYVER` must match the base image's Python.** The `0.7` base is py3.11, all
> others are py3.12. A mismatch fails at the vendored-`distributed` / bokeh steps
> because those touch `lib/python${PYVER}/site-packages`.

## Build arguments

### Structural (choose the variant)

| Parameter | Description | Default |
| --- | --- | --- |
| `BASE_IMAGE` | Coffea base image to build on top of | `coffeateam/coffea-almalinux9-noml:2026.7.0-py3.12` |
| `FLAVOUR` | Flavour label; selects `casa-flavour-<FLAVOUR>.yaml` | `noml` |
| `PYVER` | Python minor version of the base (site-packages path) | `3.12` |
| `COMBINE` | `1` to overlay `root` + `cms-combine` | `0` |

### Deployment / cluster customization

| Parameter | Description | Default |
| --- | --- | --- |
| `TAG` | Image tag used to sync the worker image (Dask Jobqueue extension) | `development` |
| `PROJECT` | Project name in the registry | `coffea-casa` |
| `REGISTRY` | Registry host | `hub.opensciencegrid.org` |
| `WORKER_IMAGE` | Worker image the scheduler spawns (dask image only) | `${REGISTRY}/${PROJECT}/cc-analysis-alma9` |
| `NB_USER` | Jupyter / HTCondor user | `cms-jovyan` |
| `NB_UID` | User UID | `6440` |
| `NB_GID` | User GID | `11265` |
| `XCACHE_HOST` | XCache host for the custom XRootD plugin | `xcache.cmsaf-dev.flatiron.hollandhpc.org` |
| `LABEXTENTION_CLUSTER` | Default cluster name (coffea_casa Dask Labextension) | `UNL HTCondor Cluster` |
| `LABEXTENTION_FACTORY_CLASS` | Dask Labextension factory class | `CoffeaCasaCluster` |
| `LABEXTENTION_FACTORY_MODULE` | Dask Labextension factory module | `coffea_casa` |
| `CONDOR_HOST` | HTCondor collector host | `red-condor.unl.edu` |
| `COLLECTOR_NAME` | HTCondor collector name | `Nebraska T2` |
| `UID_DOMAIN` | HTCondor UID domain | `unl.edu` |
| `SCHEDD_HOST` | HTCondor schedd host | `t3.unl.edu` |
| `CERT_DIR` | Secrets directory (see charts) | `/etc/cmsaf-secrets` |
| `BEARER_TOKEN_FILE` | Bearer token file location (see charts) | `/etc/cmsaf-secrets-chown/access_token` |
| `DASK_ROOT_CONFIG` | Dask config directory | `/opt/dask` |

### Custom cluster example

***Keep `TAG` consistent between the scheduler and worker images.***

```bash
cd docker/
docker build --platform linux/amd64 \
  --build-arg BASE_IMAGE=coffeateam/coffea-dak-almalinux9:2026.7.0-py3.12 \
  --build-arg FLAVOUR=dak \
  --build-arg PYVER=3.12 \
  --build-arg NB_USER="atlas-jovyan" \
  --build-arg CONDOR_HOST="red-condor.unl.edu" \
  --build-arg COLLECTOR_NAME="Nebraska T2" \
  --build-arg UID_DOMAIN="unl.edu" \
  --build-arg SCHEDD_HOST="t3.unl.edu" \
  -t hub.opensciencegrid.org/coffea-casa/cc-dask-alma9:$TAG \
  -f Dockerfile.cc-dask-alma9 .
```

## Automated builds (CI)

`.github/workflows/docker-build-test-publish.yaml` builds every image, runs the
test suite against the exact bytes, and only then publishes. Behavior by event:

- **pull request** — build + test, never push.
- **push to `master`** — publish `:development[-<flavour>]`.
- **release published** — publish `:<release tag>[-<flavour>]`.

Flavoured images carry a `-<flavour>` suffix; the **canonical** flavour (`noml`)
also publishes the bare tag, so `…/cc-dask-alma9:development` keeps resolving.
For example a push to `master` yields:

```
cc-dask-alma9:development-noml       cc-dask-alma9:development   (canonical alias)
cc-dask-alma9:development-dak
cc-dask-alma9:development-full
cc-dask-alma9:development-0.7
# …same for cc-analysis-alma9, plus:
cc-dask-combine-alma9:development
cc-analysis-combine-alma9:development
```

To add a flavour (or a flavoured combine image), add a row to the matrix
`include:` list in that workflow — no Dockerfile change needed.