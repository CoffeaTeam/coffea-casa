#!/usr/bin/env bash
# Spawn test: install z2jh with the candidate image, then use the Hub REST API
# to spawn a user server and verify it becomes ready and answers HTTP.
#
# Usage: ./ci/spawn-test.sh <image:tag>
set -euo pipefail

IMAGE="${1:?usage: spawn-test.sh <image:tag>}"
IMAGE_NAME="${IMAGE%:*}"
IMAGE_TAG="${IMAGE##*:}"
NAMESPACE="jhub-ci"
USER_NAME="ci-user"
API_TOKEN="$(openssl rand -hex 32)"

helm repo add jupyterhub https://hub.jupyter.org/helm-chart/ >/dev/null
helm repo update >/dev/null

echo "==> Installing zero-to-jupyterhub with image ${IMAGE}"
helm upgrade --install jhub-ci jupyterhub/jupyterhub \
  --namespace "$NAMESPACE" --create-namespace \
  -f ci/values-ci.yaml \
  --set singleuser.image.name="$IMAGE_NAME" \
  --set singleuser.image.tag="$IMAGE_TAG" \
  --set singleuser.image.pullPolicy=Never \
  --set hub.services.ci.apiToken="$API_TOKEN" \
  --wait --timeout 15m

echo "==> Port-forwarding the proxy"
kubectl -n "$NAMESPACE" port-forward service/proxy-public 8080:http >/dev/null 2>&1 &
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
for i in $(seq 1 60); do
  READY=$(curl -fsS "${AUTH[@]}" "$HUB/users/$USER_NAME" \
    | python3 -c "import sys,json; u=json.load(sys.stdin); s=u.get('servers',{}).get('',{}); print(s.get('ready', False))")
  PENDING=$(curl -fsS "${AUTH[@]}" "$HUB/users/$USER_NAME" \
    | python3 -c "import sys,json; u=json.load(sys.stdin); s=u.get('servers',{}).get('',{}); print(s.get('pending'))")
  echo "  attempt $i: ready=$READY pending=$PENDING"
  if [ "$READY" = "True" ]; then
    break
  fi
  # If the spawn failed outright, fail fast with logs.
  PHASE=$(kubectl -n "$NAMESPACE" get pod "jupyter-${USER_NAME}" \
    -o jsonpath='{.status.phase}' 2>/dev/null || echo "missing")
  if [ "$PHASE" = "Failed" ]; then
    echo "!! Singleuser pod failed"
    kubectl -n "$NAMESPACE" describe pod "jupyter-${USER_NAME}" || true
    kubectl -n "$NAMESPACE" logs "jupyter-${USER_NAME}" --all-containers || true
    exit 1
  fi
  sleep 10
done

if [ "$READY" != "True" ]; then
  echo "!! Server never became ready"
  kubectl -n "$NAMESPACE" describe pod "jupyter-${USER_NAME}" || true
  kubectl -n "$NAMESPACE" logs "jupyter-${USER_NAME}" --all-containers --tail=300 || true
  kubectl -n "$NAMESPACE" logs -l component=hub --tail=300 || true
  exit 1
fi

echo "==> Probing the user server through the proxy"
# The admin token is authorized to access the user's server API.
curl -fsS "${AUTH[@]}" "http://localhost:8080/user/$USER_NAME/api/status" \
  | python3 -m json.tool

echo "==> Stopping server"
curl -fsS -X DELETE "${AUTH[@]}" "$HUB/users/$USER_NAME/server" || true

echo "SPAWN TEST PASSED"