# AGENTS.md – container images (`docker/`)

Applies to everything under `docker/`. Repo-wide rules are in the root
[`AGENTS.md`](../AGENTS.md); the human-oriented description of flavours and
env files is in [`README.md`](README.md).

## Images

| Dockerfile | Image(s) | Role |
| --- | --- | --- |
| `Dockerfile.cc-dask-alma9` | `cc-dask-alma9`, `cc-dask-combine-alma9` | singleuser JupyterLab + Dask scheduler |
| `Dockerfile.cc-analysis-alma9` | `cc-analysis-alma9`, `cc-analysis-combine-alma9` | Dask / HTCondor worker |
| `Dockerfile.histserv-alma9` | `histserv-alma9` | histogram service |

Build args (see the matrix in `.github/workflows/docker-build-test-publish.yaml`
for current values): `BASE_IMAGE`, `FLAVOUR` (`noml` = canonical, `dak`,
`full`, `0.7`), `PYVER`, `COMBINE` (`0`/`1`).

Package sets come from `env/*.yaml`, applied in order (later wins):
`casa-common` → `casa-dask` or `casa-analysis` → `casa-flavour-<FLAVOUR>` →
`casa-combine` (if `COMBINE=1`).

- Put a package in the **narrowest** file that needs it. Version-sensitive pins
  (numpy, xrootd, numba) go in the flavour files, not `casa-common.yaml`.
- There is no separate combine Dockerfile; don't create one.

## Build & test

From the repo root (canonical image):

```sh
hadolint --config .hadolint.yaml docker/Dockerfile.cc-dask-alma9
docker build -f docker/Dockerfile.cc-dask-alma9 \
  --build-arg BASE_IMAGE=coffeateam/coffea-almalinux9-noml:2026.9.0-py3.12 \
  --build-arg FLAVOUR=noml --build-arg PYVER=3.12 --build-arg COMBINE=0 \
  -t cc-dask-alma9:dev docker/

container-structure-test test --image cc-dask-alma9:dev --config ci/structure-tests.yaml
docker run --rm -e COFFEA_CASA_IMAGE_TESTS=1 -e CASA_FLAVOUR=noml -e CASA_PYVER=3.12 \
  -v "$PWD/tests:/tests:ro" cc-dask-alma9:dev \
  bash -c "pip install --quiet --user pytest && python -m pytest /tests/test_image_smoke.py -v"
```

Worker image (`cc-analysis-alma9`): use `-e COFFEA_CASA_ANALYSIS_TESTS=1`
(plus `-e CASA_COMBINE=0|1`), `--entrypoint bash`, and
`/tests/test_analysis_smoke.py`. Structure tests apply to singleuser images
only. Copy the exact invocations from the workflow if in doubt.
Changes to `prepare-env/worker-args.sh` must pass `bats tests/worker-args.bats`.

Builds are large (multi-GB base images); if you can't build locally, at least
run hadolint and say in the PR which flavours were built.

## Rules

- Keep hadolint clean at the `error` threshold. The ignored rules in
  `.hadolint.yaml` (DL3013, DL3033, DL3003, DL3059) are deliberate; don't add
  new ignores without a comment explaining why.
- The singleuser contract is checked by `ci/structure-tests.yaml`: UID `6440`,
  user `cms-jovyan`, port `8888`, entrypoint
  `tini -g -- /usr/local/bin/prepare-env.sh`, `DASK_ROOT_CONFIG=/opt/dask`.
  If you change any of these, update the structure tests **and** the Helm
  chart in the same PR.
- Startup scripts (`jupyterhub/start*.sh`, `prepare-env/*.sh`) must stay
  POSIX/bash-safe and executable; preserve file modes.
- `certs/` holds public CA certificates only. Never add private keys, proxies
  or tokens to any image.
- Changing a base image tag affects every flavour in the CI matrix and the
  chart test (`chart-test.yaml` pins the same tag) – update both together, in
  a dedicated PR.
