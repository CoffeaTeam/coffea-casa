#!/usr/bin/env python3
"""
Real end-to-end test of coffea_casa.taskvine against a live HTCondor pool (#167).

Like ci/htcondor_cluster_test.py, but for TaskVine: a TLS TaskVine manager runs
here, CoffeaCasaVineWorkers submits a worker to the htcondor/mini pool, the
actual cc-analysis-alma9 image's entrypoint (prepare-env.sh -> worker-args.sh)
starts vine_worker from the job's ClassAd, and the worker runs tasks sent by
the manager - the second one reading a temp file the first left on the worker,
as vine_reduce's tasks do. (The pool has one worker, so worker-to-worker
transfers through the forwarded "vine" port are not exercised.)

Env vars:
  WORKER_IMAGE  - docker image tag for the worker (required)
  HOST_IP       - address the worker container reaches this host on
"""
import os
import sys

import ndcctools.taskvine as vine

import coffea_casa.config  # noqa: F401 - registers jobqueue.coffea-casa defaults
from coffea_casa import CoffeaCasaVineWorkers, vine_manager


def main():
    manager = vine_manager()
    workers = CoffeaCasaVineWorkers(manager, cores=1, memory_mb=512, disk_mb=1024,
                                    worker_image=os.environ["WORKER_IMAGE"],
                                    idle_timeout=120)
    print("=== submit description ===", flush=True)
    print(workers.submit_description(1), flush=True)
    workers.submit(1)

    try:
        # A file produced on the worker and consumed by a second task: the
        # result stays on the worker (temp file), as vine_reduce's do.
        produced = manager.declare_temp()
        t1 = vine.Task("python -c 'print(41 + 1)' > out.txt")
        t1.add_output(produced, "out.txt")
        manager.submit(t1)
        t2 = vine.Task("cat in.txt")
        t2.add_input(produced, "in.txt")
        manager.submit(t2)

        done = {}
        while not manager.empty():
            task = manager.wait(300)
            if task is None:
                print("FAILED: no task finished within 300s", flush=True)
                for path in workers.fetch_worker_logs():
                    print(f"=== {path} ===\n{path.read_text(errors='replace')}", flush=True)
                sys.exit(1)
            print(f"task {task.id}: result={task.result} exit={task.exit_code} "
                  f"output={task.output!r}", flush=True)
            done[task.id] = task

        assert t1.successful() and t2.successful(), "a task failed"
        assert t2.output.strip() == "42", f"expected 42, got {t2.output!r}"
        print("SUCCESS: HTCondor docker-universe vine_worker ran TaskVine tasks", flush=True)
    finally:
        workers.close()


if __name__ == "__main__":
    main()
