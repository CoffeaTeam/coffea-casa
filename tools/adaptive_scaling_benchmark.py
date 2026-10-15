#!/usr/bin/env python3
"""
Benchmark adaptive-scaling settings of CoffeaCasaCluster (issue #81).

Runs the same workload on a fresh cluster for each scaling configuration and
reports wall time, peak and total workers, worker-seconds used and how long
workers took to start. Meant to be run on a coffea-casa hub, since the
numbers depend on HTCondor scheduling and image/env startup times.

In a notebook (kernel in the env you want to measure):

    import sys; sys.path.insert(0, "/path/to/coffea-casa/tools")
    from adaptive_scaling_benchmark import run_benchmark, synthetic_workload, plot

    results = run_benchmark(workload=synthetic_workload(n_tasks=400, mean_s=3))
    plot(results)

or from a terminal:

    python -u tools/adaptive_scaling_benchmark.py --tasks 400 --mean 3 --repeats 2

To benchmark a real analysis, pass ``workload=fn`` where ``fn(client)`` runs it
and blocks until the results are back (e.g. a coffea ``Runner`` call or
``dask.compute``). Results, including the worker-count timelines, are written
to ``~/adaptive-bench/<timestamp>/results.json``.
"""

import argparse
import json
import math
import random
import statistics
import sys
import threading
import time
from pathlib import Path

# Each configuration is either {"adapt": <cluster.adapt kwargs>} or
# {"scale": <n>}. adapt kwargs left out come from the distributed.adaptive
# dask config (docker/dask/dask.yaml).
DEFAULT_CONFIGS = {
    "adapt-default": {"adapt": {"minimum": 1, "maximum": 50}},
    "adapt-30s": {"adapt": {"minimum": 1, "maximum": 50,
                            "target_duration": "30s"}},
    "adapt-60s-slow-down": {"adapt": {"minimum": 1, "maximum": 50,
                                      "target_duration": "60s",
                                      "wait_count": 30}},
    "scale-10": {"scale": 10},
}


def cap_workers(spec, n):
    """Return ``spec`` with its worker count (adapt maximum or scale) capped at n."""
    if "adapt" in spec:
        adapt = dict(spec["adapt"])
        adapt["maximum"] = min(adapt.get("maximum", n), n)
        adapt["minimum"] = min(adapt.get("minimum", 0), n)
        return {"adapt": adapt}
    return {"scale": min(spec["scale"], n)}


def burn(duration, seed):
    """Keep one core busy for ``duration`` seconds (stands in for one chunk)."""
    end = time.perf_counter() + duration
    x = seed
    while time.perf_counter() < end:
        x = (x * 1103515245 + 12345) % 2**31
    return x


def synthetic_workload(n_tasks=400, mean_s=3.0, spread=0.5, phases=1,
                       gap_s=0.0, seed=0):
    """Return a workload of ``phases`` batches of CPU-bound tasks.

    Task durations are log-normal with mean ``mean_s`` seconds, so the total
    work per phase is about ``n_tasks * mean_s`` core-seconds. ``gap_s`` idles
    between phases, which exercises scale-down. Every call of the returned
    function uses the same durations, so configurations are comparable.
    """
    def run(client):
        rng = random.Random(seed)
        mu = math.log(mean_s) - spread ** 2 / 2
        for phase in range(phases):
            durations = [rng.lognormvariate(mu, spread) for _ in range(n_tasks)]
            futures = client.map(burn, durations, range(n_tasks), pure=False)
            client.gather(futures)
            if gap_s and phase < phases - 1:
                time.sleep(gap_s)

    run.description = (f"synthetic: {phases} x {n_tasks} tasks, mean {mean_s}s, "
                       f"gap {gap_s}s (~{phases * n_tasks * mean_s:.0f} core-s)")
    return run


def _scheduler_workers(dask_scheduler):
    return list(dask_scheduler.workers)


class _Monitor:
    """Poll requested (cluster.plan) and connected workers in the background.

    HTCondor names workers after their job id, which doesn't match the plan's
    names, so startup lag pairs the k-th requested worker with the k-th worker
    to connect. That is exact while only scaling up and an approximation once
    pending workers are cancelled by a scale-down.
    """

    def __init__(self, client, cluster, interval):
        self.client, self.cluster, self.interval = client, cluster, interval
        self.samples = []          # (t, requested, connected)
        self.request_times = []    # first time each planned worker was seen
        self.arrival_times = []    # first time each worker connected
        self._seen_plan, self._seen_workers = set(), set()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self, t0):
        self.t0 = t0
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
        self._poll()

    def _poll(self):
        t = time.monotonic() - self.t0
        try:
            plan = set(self.cluster.plan)
            workers = set(self.client.run_on_scheduler(_scheduler_workers))
        except Exception:  # cluster shutting down, transient comm error
            return
        self.request_times += [t] * len(plan - self._seen_plan)
        self.arrival_times += [t] * len(workers - self._seen_workers)
        self._seen_plan |= plan
        self._seen_workers |= workers
        self.samples.append((t, len(plan), len(workers)))

    def _loop(self):
        while not self._stop.wait(self.interval):
            self._poll()


def _integral(samples, index, t_end):
    """Time integral of samples[i][index] (a step function) up to t_end."""
    total = 0.0
    for (t, *values), (t_next, *_) in zip(samples, samples[1:] + [(t_end,)]):
        total += values[index - 1] * (min(t_next, t_end) - t)
    return total


def _summarize(name, spec, mon, wall):
    lags = [a - r for r, a in zip(mon.request_times, mon.arrival_times)]
    samples = mon.samples
    return {
        "config": name,
        "spec": spec,
        "wall_s": round(wall, 1),
        "first_worker_s": (round(mon.arrival_times[0], 1)
                           if mon.arrival_times else None),
        "peak_requested": max((s[1] for s in samples), default=0),
        "peak_connected": max((s[2] for s in samples), default=0),
        "workers_started": len(mon.arrival_times),
        "worker_s": round(_integral(samples, 2, wall)),
        "requested_worker_s": round(_integral(samples, 1, wall)),
        "startup_median_s": round(statistics.median(lags), 1) if lags else None,
        "startup_max_s": round(max(lags), 1) if lags else None,
        "timeline": samples,
    }


def run_one(name, spec, workload, cluster_factory, cluster_kwargs,
            poll_interval=1.0):
    """Run ``workload`` once on a fresh cluster scaled according to ``spec``."""
    from dask.distributed import Client

    cluster = cluster_factory(**cluster_kwargs)
    client = Client(cluster)
    try:
        mon = _Monitor(client, cluster, poll_interval)
        t0 = time.monotonic()
        mon.start(t0)
        if "adapt" in spec:
            cluster.adapt(**spec["adapt"])
        else:
            cluster.scale(spec["scale"])
        workload(client)
        wall = time.monotonic() - t0
        mon.stop()
        return _summarize(name, spec, mon, wall)
    finally:
        _drain(client, cluster)
        client.close()
        cluster.close()


def _drain(client, cluster, timeout_s=60):
    """Stop the workers and wait for them to leave before closing the cluster.

    Closing the scheduler with workers still connected makes distributed log a
    CancelledError traceback per worker.
    """
    try:
        if cluster._adaptive is not None:
            cluster._adaptive.stop()
        cluster.scale(0)
        deadline = time.monotonic() + timeout_s
        while (client.run_on_scheduler(_scheduler_workers)
               and time.monotonic() < deadline):
            time.sleep(1)
    except Exception:  # best effort; close() follows anyway
        pass


def run_benchmark(workload=None, configs=None, repeats=1, cluster_factory=None,
                  cluster_kwargs=None, out_dir="~/adaptive-bench",
                  cooldown_s=30, poll_interval=1.0):
    """Run ``workload`` under each configuration, ``repeats`` times.

    The configuration order is rotated on every repeat so that changes in
    HTCondor queue load don't always favour the same configuration. Returns
    the list of per-run summaries and writes them to ``out_dir``.
    """
    import cloudpickle
    import dask

    # Ship this module's functions (burn) to workers by value: the workers
    # don't have this file on their PYTHONPATH.
    if __name__ != "__main__":
        cloudpickle.register_pickle_by_value(sys.modules[__name__])

    if cluster_factory is None:
        from coffea_casa import CoffeaCasaCluster as cluster_factory
    workload = workload or synthetic_workload()
    configs = configs or DEFAULT_CONFIGS
    cluster_kwargs = cluster_kwargs or {}
    out = Path(out_dir).expanduser() / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)

    print(f"Workload: {getattr(workload, 'description', workload)}")
    print(f"Adaptive defaults: {dask.config.get('distributed.adaptive')}")
    names = list(configs)
    results = []
    for rep in range(repeats):
        order = names[rep % len(names):] + names[:rep % len(names)]
        for name in order:
            print(f"[{rep + 1}/{repeats}] {name} ...", flush=True)
            try:
                result = run_one(name, configs[name], workload, cluster_factory,
                                 cluster_kwargs, poll_interval)
            except Exception as e:
                result = {"config": name, "spec": configs[name], "error": repr(e)}
                print(f"  failed: {e!r}")
            result["repeat"] = rep
            results.append(result)
            if "error" not in result:
                print("  " + _format_row(result))
            (out / "results.json").write_text(json.dumps({
                "workload": getattr(workload, "description", repr(workload)),
                "adaptive_defaults": dask.config.get("distributed.adaptive"),
                "results": results,
            }, indent=1, default=str))
            time.sleep(cooldown_s)  # let HTCondor remove the previous jobs

    print()
    print_table(results)
    print(f"\nSaved to {out / 'results.json'}")
    return results


_COLUMNS = ["wall_s", "first_worker_s", "peak_requested", "peak_connected",
            "workers_started", "worker_s", "startup_median_s", "startup_max_s"]


def _format_row(r):
    return "  ".join(f"{c}={r.get(c)}" for c in _COLUMNS)


def print_table(results):
    """Print the runs, and per-configuration medians when there are repeats."""
    ok = [r for r in results if "error" not in r]
    width = max([len(r["config"]) for r in ok] + [6])
    print(f"{'config':<{width}}  " + "  ".join(f"{c:>16}" for c in _COLUMNS))
    for r in ok:
        print(f"{r['config']:<{width}}  "
              + "  ".join(f"{str(r.get(c)):>16}" for c in _COLUMNS))
    if len(ok) > len({r["config"] for r in ok}):
        print("\nMedian per configuration:")
        for name in dict.fromkeys(r["config"] for r in ok):
            runs = [r for r in ok if r["config"] == name]
            cells = []
            for c in _COLUMNS:
                vals = [r[c] for r in runs if r.get(c) is not None]
                cells.append(f"{statistics.median(vals) if vals else None!s:>16}")
            print(f"{name:<{width}}  " + "  ".join(cells))


def plot(results, ax=None):
    """Plot connected workers over time for each run (needs matplotlib)."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))
    for r in results:
        if "error" in r:
            continue
        t, _, connected = zip(*r["timeline"]) if r["timeline"] else ((), (), ())
        ax.step(t, connected, where="post",
                label=f"{r['config']} (rep {r['repeat']}, {r['wall_s']}s)")
    ax.set_xlabel("time since scale/adapt (s)")
    ax.set_ylabel("connected workers")
    ax.legend(fontsize="small")
    return ax


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--tasks", type=int, default=400, help="tasks per phase")
    parser.add_argument("--mean", type=float, default=3.0,
                        help="mean task duration in seconds")
    parser.add_argument("--phases", type=int, default=1)
    parser.add_argument("--gap", type=float, default=0.0,
                        help="idle seconds between phases")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--configs", nargs="+", choices=list(DEFAULT_CONFIGS),
                        help="subset of configurations to run")
    parser.add_argument("--max-workers", type=int,
                        help="cap adapt maximum and scale count (e.g. the "
                             "number of HTCondor slots available)")
    parser.add_argument("--cooldown", type=float, default=30)
    parser.add_argument("--out", default="~/adaptive-bench")
    args = parser.parse_args()

    configs = {k: DEFAULT_CONFIGS[k] for k in (args.configs or DEFAULT_CONFIGS)}
    if args.max_workers:
        configs = {k: cap_workers(v, args.max_workers) for k, v in configs.items()}
    run_benchmark(
        workload=synthetic_workload(args.tasks, args.mean, phases=args.phases,
                                    gap_s=args.gap),
        configs=configs, repeats=args.repeats, out_dir=args.out,
        cooldown_s=args.cooldown)


if __name__ == "__main__":
    main()
