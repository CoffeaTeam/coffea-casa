#!/usr/bin/env bash
# Chart spawn test: against an already-installed coffea-casa chart release,
# use the Hub REST API to spawn a user server with the chart's default
# singleuser profile and verify it becomes ready and answers HTTP.
#
# Unlike ci/spawn-test.sh (which installs the upstream jupyterhub chart
# directly to test a candidate docker image), this targets our own chart's
# release/wiring - profileList, hub-extra-config-d mounts, kubespawner
# overrides, etc. Authenticates with the static `hub.services.test.apiToken`
# already committed in values.yaml, so no --set/secret plumbing is needed.
#
# Usage: ./ci/chart-spawn-test.sh <namespace>
set -euo pipefail

NAMESPACE="${1:?usage: chart-spawn-test.sh <namespace>}"
USER_NAME="ci-user"
API_TOKEN="ssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssssss"

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

echo "==> Stopping server"
curl -fsS -X DELETE "${AUTH[@]}" "$HUB/users/$USER_NAME/server" || true

echo "CHART SPAWN TEST PASSED"
