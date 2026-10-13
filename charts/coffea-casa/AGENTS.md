# AGENTS.md – Helm chart (`charts/coffea-casa`)

Applies to everything under `charts/coffea-casa/`. Repo-wide rules are in the
root [`AGENTS.md`](../../AGENTS.md). Detailed local-cluster instructions for
humans are in [`docs/DEVNOTES.md`](docs/DEVNOTES.md).

## What this is

A wrapper chart around the Zero to JupyterHub `jupyterhub` chart (dependency
version pinned in `Chart.yaml`). Most configuration lives under the
`jupyterhub:` key in values files; coffea-casa-specific templates are in
`templates/` and extra hub config in `files/hub-extra/`.

- `version` in `Chart.yaml` is a placeholder set by chartpress – don't edit it.
- `values.yaml` – dev/CI defaults.
- `values-prod.yaml`, `values-cmsaf-prod.yaml` – **production**; only change
  when explicitly asked.
- Values files are deployed **one at a time**, never merged together. A change
  must work with each of them independently.

## Commands

Run from `charts/coffea-casa/` (same as `chart-test.yaml`):

```sh
helm dependency update
for f in values.yaml values-prod.yaml values-cmsaf-prod.yaml; do
  helm lint . -f "$f" && helm template coffea-casa . -f "$f" > /dev/null
done
```

Full install test (what CI's `install` job does) – needs Docker + kind:

```sh
kind create cluster --name cc-chart-test
docker build -f docker/Dockerfile.cc-dask-alma9 \
  --build-arg BASE_IMAGE=coffeateam/coffea-almalinux9-noml:2026.9.0-py3.12 \
  --build-arg FLAVOUR=noml --build-arg PYVER=3.12 --build-arg COMBINE=0 \
  -t coffea-casa/cc-dask-alma9:chart-ci docker/          # from repo root
kind load docker-image coffea-casa/cc-dask-alma9:chart-ci --name cc-chart-test
kubectl create namespace coffea-casa-ci
helm upgrade --install coffea-casa . -f values.yaml -f ../../ci/values-chart-ci.yaml \
  -n coffea-casa-ci --wait --timeout 10m
../../ci/chart-spawn-test.sh coffea-casa-ci             # spawns a real user server
```

Check `.github/workflows/chart-test.yaml` for the current base image tag
before copying the build args above.

## Rules

- **Schema:** values are validated against `schema.yaml`. When adding or
  renaming a value, update `schema.yaml` in the same change, then regenerate
  with `python tools/generate-json-schema.py` (from repo root) and make sure
  `helm lint` still passes for all three values files.
- `helm template` passing is not enough: keys under `kubespawner_override`,
  `hub.extraConfig` and ConfigMap globs only fail at runtime. If you touch
  those, say in the PR whether the kind spawn test was run.
- `files/hub-extra/` is packaged by `templates/hub-extra-config-d.yaml`:
  `*.{py,html}` go into `data`, `*.bin` into `binaryData`. Any binary file
  must use the `.bin` suffix (e.g. `logo.png.bin`) – a single non-UTF-8 file
  matched by the text glob silently empties the whole ConfigMap. New text
  file types need the glob extended.
- The chart and the singleuser image must agree (entrypoint, UID `6440`, env
  vars). If you change one, check `docker/` and `ci/structure-tests.yaml`.
- Don't bump the `jupyterhub` dependency version as a side effect of another
  change.
- Never put secrets in values files; use existing secret templates
  (`templates/af-secrets.yaml`) and reference them.
