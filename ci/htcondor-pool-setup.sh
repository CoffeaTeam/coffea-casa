#!/usr/bin/env bash
# Stand up a disposable, all-in-one HTCondor pool (htcondor/mini: collector +
# negotiator + schedd + startd in one container) with Docker-universe jobs
# enabled, for htcondor-cluster-test.yml. Docker-outside-of-Docker: the pool
# container talks to the *host's* dockerd via the mounted socket, so images
# built on the runner are already visible to it - no image push/load needed.
#
# Usage: ./ci/htcondor-pool-setup.sh <container-name>
set -euo pipefail

NAME="${1:?usage: htcondor-pool-setup.sh <container-name>}"

echo "==> Starting $NAME"
docker run -d --name "$NAME" --privileged \
  -v /var/run/docker.sock:/var/run/docker.sock \
  htcondor/mini:24.0-el9 >/dev/null

echo "==> Waiting for condor_status to respond"
for _ in $(seq 1 30); do
  docker exec "$NAME" condor_status >/dev/null 2>&1 && break
  sleep 2
done

echo "==> Installing the docker CLI (image has none, only the daemon socket)"
docker exec "$NAME" bash -c '
  curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz -o /tmp/docker.tgz
  tar -xzf /tmp/docker.tgz -C /tmp
  cp /tmp/docker/docker /usr/bin/docker
  chmod +x /usr/bin/docker
'

# The mounted socket is root:root/0660 on the runner; the condor daemon user
# has no supplementary groups, so it cannot reach it without this. The docker
# CLI also needs a writable $HOME for its config.json, which the condor user
# does not otherwise have (see STARTER.ENV/STARTD.ENV below).
echo "==> Granting the condor daemon user access to the docker socket"
docker exec "$NAME" chmod 666 /var/run/docker.sock
docker exec "$NAME" bash -c 'mkdir -p /var/lib/condor/.docker && chown -R condor:condor /var/lib/condor'

echo "==> Enabling Docker-universe jobs and restarting the pool"
docker exec "$NAME" bash -c 'cat > /etc/condor/config.d/50-docker.conf <<EOF
STARTER.ENV = HOME=/var/lib/condor
STARTD.ENV = HOME=/var/lib/condor
EOF'
docker exec "$NAME" condor_restart -master

echo "==> Waiting for the startd to advertise HasDocker=true"
for _ in $(seq 1 30); do
  has_docker=$(docker exec "$NAME" condor_status -startd -af HasDocker 2>/dev/null || true)
  [ "$has_docker" = "true" ] && { echo "HasDocker=true"; exit 0; }
  sleep 2
done

echo "!! startd never advertised HasDocker=true"
docker exec "$NAME" bash -c 'grep -i docker /var/log/condor/StarterLog* 2>/dev/null' || true
exit 1
