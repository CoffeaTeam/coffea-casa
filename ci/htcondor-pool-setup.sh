#!/usr/bin/env bash
# Install a disposable, all-in-one HTCondor pool (minicondor: collector +
# negotiator + schedd + startd) *natively* on this machine, with Docker-
# universe jobs enabled, for htcondor-cluster-test.yml.
#
# This must run natively (not inside a container talking to the host's
# dockerd over a mounted socket) - HTCondor's docker universe bind-mounts
# each job's scratch directory into the worker container, and the startd
# and dockerd need to agree on what that path actually contains. Docker-
# outside-of-Docker breaks this: the scratch dir the startd populates lives
# in the *calling* container's own filesystem, invisible to the outer
# dockerd that resolves the bind-mount source, so the worker container gets
# an empty auto-vivified directory instead of the real .job.ad etc. Running
# condor as a native process on the same host as the runner's own native
# dockerd avoids that mismatch entirely.
#
# Usage: ./ci/htcondor-pool-setup.sh
set -euo pipefail

echo "==> Installing HTCondor (minicondor) natively"
curl -fsSL https://get.htcondor.org | sudo /bin/bash -s -- --no-dry-run

echo "==> Granting the condor daemon user access to the docker socket"
sudo usermod -aG docker condor
# The docker CLI needs a writable $HOME for its config.json, which the
# condor daemon user does not otherwise have.
sudo mkdir -p /var/lib/condor/.docker
sudo chown -R condor:condor /var/lib/condor

echo "==> Enabling Docker-universe jobs and restarting the pool"
sudo bash -c 'cat > /etc/condor/config.d/50-docker.conf' <<'EOF'
STARTER.ENV = HOME=/var/lib/condor
STARTD.ENV = HOME=/var/lib/condor
# By default HTCondor always `docker pull`s the image, even one that only
# exists in the local Docker image cache (e.g. one this same workflow just
# built), and fails with "pull access denied" since it isn't a real
# registry image. This trusts locally-cached images instead.
DOCKER_TRUST_LOCAL_IMAGES = true
DOCKER_IMAGE_CACHE_SIZE = 0
EOF
sudo condor_restart -master

echo "==> Waiting for the startd to advertise HasDocker=true"
for _ in $(seq 1 30); do
  has_docker=$(condor_status -startd -af HasDocker 2>/dev/null || true)
  [ "$has_docker" = "true" ] && { echo "HasDocker=true"; exit 0; }
  sleep 2
done

echo "!! startd never advertised HasDocker=true"
sudo bash -c 'grep -i docker /var/log/condor/StarterLog* 2>/dev/null' || true
exit 1
