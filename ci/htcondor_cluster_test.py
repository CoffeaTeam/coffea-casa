#!/usr/bin/env python3
"""
Real end-to-end test of CoffeaCasaCluster against a live HTCondor pool.

Run inside a container that has network access to an htcondor/mini pool
(collector+negotiator+schedd+startd in one) with Docker-universe enabled,
and with the coffea-casa Python package + its deps installed. Exercises the
real submission path: condor_submit, matchmaking, `docker create`/`docker
start` of the actual cc-analysis-alma9 worker image, that image's own
ENTRYPOINT (prepare-env.sh -> worker-args.sh building the dask-worker
command line from the job's real HTCondor ClassAd), and a real dask
computation over the wire - not a mock.

Env vars:
  WORKER_IMAGE  - docker image tag for the dask worker (required)
"""
import os
import sys
import time

import coffea_casa.config  # noqa: E402,F401 - registers jobqueue.coffea-casa defaults

from coffea_casa import CoffeaCasaCluster
from distributed import Client


def main():
    worker_image = os.environ["WORKER_IMAGE"]

    cluster = CoffeaCasaCluster(
        cores=1,
        memory="512MiB",
        disk="512MiB",
        force_tcp=True,
        worker_image=worker_image,
        # prepare-env-cc-analysis.sh polls the job ClassAd for up to 30s
        # waiting for HTCondor to resolve dask_HostPort/nanny_HostPort (the
        # container's mapped host ports), and explicitly skips that wait
        # when GITHUB_ACTIONS=true - the script's own escape hatch for
        # exactly this kind of ephemeral/CI pool. Propagate it into the
        # worker container so this test isn't paying that wait every run.
        job_extra_directives={"environment": "GITHUB_ACTIONS=true"},
    )

    print("=== job script CoffeaCasaCluster submits ===", flush=True)
    print(cluster.job_script(), flush=True)

    cluster.scale(1)
    client = Client(cluster)

    for i in range(40):
        n_workers = len(client.scheduler_info().get("workers", {}))
        print(f"attempt {i}: workers={n_workers}", flush=True)
        if n_workers >= 1:
            break
        time.sleep(3)
    else:
        print("FAILED: no HTCondor-submitted worker connected within timeout", flush=True)
        sys.exit(1)

    result = client.submit(lambda x: x + 1, 41).result(timeout=60)
    assert result == 42, f"expected 42, got {result}"
    print("SUCCESS: real HTCondor docker-universe worker computed a task", flush=True)


if __name__ == "__main__":
    main()
