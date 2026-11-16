#!/usr/bin/env bash
# Chart spawn test: against an already-installed coffea-casa chart release,
# use the Hub REST API to spawn a user server with the chart's default
# singleuser profile, verify it becomes ready and answers HTTP, and verify
# the dask-labextension LocalCluster factory actually starts inside it.
#
# Unlike ci/spawn-test.sh (which installs the upstream jupyterhub chart
# directly to test a candidate docker image), this targets our own chart's
# release/wiring - profileList, hub-extra-config-d mounts, kubespawner
# overrides, etc. Authenticates as the `ci` admin service declared in
# ci/values-chart-ci.yaml, whose token must be passed in HUB_API_TOKEN (the
# same value given to helm via --set jupyterhub.hub.services.ci.apiToken=...).
#
# Usage: HUB_API_TOKEN=... ./ci/chart-spawn-test.sh <namespace>
set -euo pipefail

NAMESPACE="${1:?usage: chart-spawn-test.sh <namespace>}"
USER_NAME="ci-user"
API_TOKEN="${HUB_API_TOKEN:?HUB_API_TOKEN must be set to the ci service token}"

echo "==> Port-forwarding the proxy"
kubectl -n "$NAMESPACE" port-forward service/proxy-public 8080:80 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 5

HUB="http://localhost:8080/hub/api"
AUTH=(-H "Authorization: token ${API_TOKEN}")

echo "==> Hub info:"
curl -fsS "${AUTH[@]}" "$HUB/info" | python3 -m json.tool || true

echo "==> Creating user and requesting spawn"
curl -fsS -X POST "${AUTH[@]}" "$HUB/users/$USER_NAME" >/dev/null || true
curl -fsS -X POST "${AUTH[@]}" "$HUB/users/$USER_NAME/server" -d '{}' || true

echo "==> Waiting for server to become ready (max 10 min)"
READY="False"
for i in $(seq 1 60); do
  READY=$(curl -fsS "${AUTH[@]}" "$HUB/users/$USER_NAME" \
    | python3 -c "import sys,json; u=json.load(sys.stdin); s=u.get('servers',{}).get('',{}); print(s.get('ready', False))")
  echo "  attempt $i: ready=$READY"
  if [ "$READY" = "True" ]; then
    break
  fi
  PHASE=$(kubectl -n "$NAMESPACE" get pod -l component=singleuser-server \
    -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "missing")
  if [ "$PHASE" = "Failed" ]; then
    echo "!! Singleuser pod failed"
    kubectl -n "$NAMESPACE" describe pod -l component=singleuser-server || true
    kubectl -n "$NAMESPACE" logs -l component=singleuser-server --all-containers || true
    exit 1
  fi
  sleep 10
done

if [ "$READY" != "True" ]; then
  echo "!! Server never became ready"
  kubectl -n "$NAMESPACE" describe pod -l component=singleuser-server || true
  kubectl -n "$NAMESPACE" logs -l component=singleuser-server --all-containers --tail=300 || true
  kubectl -n "$NAMESPACE" logs -l component=hub --tail=300 || true
  exit 1
fi

echo "==> Probing the user server through the proxy"
curl -fsS "${AUTH[@]}" "http://localhost:8080/user/$USER_NAME/api/status" \
  | python3 -m json.tool

# Regression test for the dask-labextension LocalCluster crash: without facility
# certs mounted, the image's dask_tls.yaml (ca-file /etc/cmsaf-secrets/ca.pem)
# makes LocalCluster() fail with "Cluster failed to start: [Errno 2] No such
# file or directory". values-dev.yaml clears it via the chart's daskConfig,
# mounted at /usr/local/etc/dask. This only reproduces inside the actual
# spawned pod, not via helm template/lint.
POD=$(kubectl -n "$NAMESPACE" get pod -l component=singleuser-server -o jsonpath='{.items[0].metadata.name}')
echo "==> Verifying the chart daskConfig is mounted and applied (pod: $POD)"
if ! kubectl -n "$NAMESPACE" exec "$POD" -c notebook -- python3 -c "
import dask.config
cls = dask.config.get('labextension.factory.class')
assert cls == 'LocalCluster', cls
print('labextension.factory.class =', cls)
"; then
  echo "!! chart daskConfig (values-dev.yaml) not applied in the singleuser pod"
  kubectl -n "$NAMESPACE" exec "$POD" -c notebook -- cat /usr/local/etc/dask/coffea-casa.yaml || true
  exit 1
fi

echo "==> Verifying the dask-labextension LocalCluster factory starts (pod: $POD)"
if ! kubectl -n "$NAMESPACE" exec "$POD" -c notebook -- python3 -c "
from dask.distributed import LocalCluster
c = LocalCluster()
print('LocalCluster started OK:', c)
c.close()
"; then
  echo "!! LocalCluster failed to start inside the spawned singleuser pod"
  kubectl -n "$NAMESPACE" exec "$POD" -c notebook -- cat /opt/dask/dask_tls.yaml || true
  kubectl -n "$NAMESPACE" exec "$POD" -c notebook -- cat /usr/local/etc/dask/coffea-casa.yaml || true
  exit 1
fi

echo "==> Stopping server"
curl -fsS -X DELETE "${AUTH[@]}" "$HUB/users/$USER_NAME/server" || true

echo "CHART SPAWN TEST PASSED"
