#!/usr/bin/env bash
# Assert the jupyterhub version inside the singleuser IMAGE is compatible with
# the Hub version that the z2jh CHART_VERSION deploys.
#
# "Compatible" here = same major version. JupyterHub requires the Hub and the
# singleuser server to be closely matched; a major-version gap (e.g. Hub 1.x vs
# singleuser 5.x) breaks the spawn handshake (missing JUPYTERHUB_SERVICE_URL etc).
#
# Usage: ./ci/check-version-skew.sh <image:tag> <z2jh-chart-version>
#   e.g. ./ci/check-version-skew.sh hub.opensciencegrid.org/coffea-casa/cc-dask-alma9:dev 4.2.0
set -euo pipefail

IMAGE="${1:?usage: check-version-skew.sh <image:tag> <chart-version>}"
CHART_VERSION="${2:?usage: check-version-skew.sh <image:tag> <chart-version>}"

# --- 1. jupyterhub version baked into the singleuser image -------------------
IMAGE_HUB_VER="$(docker run --rm "$IMAGE" \
  python -c "import jupyterhub; print(jupyterhub._version.__version__)" 2>/dev/null \
  || docker run --rm "$IMAGE" jupyterhub-singleuser --version)"
IMAGE_HUB_VER="$(echo "$IMAGE_HUB_VER" | tr -d '[:space:]')"

# --- 2. Hub version the chart ships (chart's appVersion) ---------------------
helm repo add jupyterhub https://hub.jupyter.org/helm-chart/ >/dev/null 2>&1 || true
helm repo update >/dev/null
CHART_HUB_VER="$(helm show chart jupyterhub/jupyterhub --version "$CHART_VERSION" \
  | awk '/^appVersion:/ {print $2}' | tr -d '"'"'"'[:space:]')"

echo "singleuser image jupyterhub : ${IMAGE_HUB_VER}"
echo "chart ${CHART_VERSION} deploys Hub : ${CHART_HUB_VER}"

# --- 3. compare major versions ----------------------------------------------
img_major="${IMAGE_HUB_VER%%.*}"
hub_major="${CHART_HUB_VER%%.*}"

if [ -z "$img_major" ] || [ -z "$hub_major" ]; then
  echo "ERROR: could not parse one of the versions" >&2
  exit 2
fi

if [ "$img_major" != "$hub_major" ]; then
  echo "::error::JupyterHub version skew: image ships ${IMAGE_HUB_VER} (major ${img_major}) but chart ${CHART_VERSION} deploys Hub ${CHART_HUB_VER} (major ${hub_major}). Spawns will fail. Align the Dockerfile jupyterhub pin with the chart's Hub version."
  exit 1
fi

echo "OK: image and chart Hub share major version ${img_major}."