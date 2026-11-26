Running Analyses with TaskVine
==============================

Besides Dask, coffea-casa can run analyses with `TaskVine
<https://cctools.readthedocs.io/en/stable/taskvine>`_, usually through
`VineReduce <https://github.com/cooperative-computing-lab/vine-reduce>`_ (see
the `Vine CMS Analysis Stack
<https://github.com/cooperative-computing-lab/vine-cms-analysis-stack>`_ for
examples). The TaskVine manager runs in your notebook, and
``coffea_casa.CoffeaCasaVineWorkers`` starts TaskVine workers as HTCondor jobs
on the facility's worker image.

.. note::
   TaskVine and VineReduce are included in the coffea 2025+ images (``noml``,
   ``dak`` and ``full``), not in the coffea 0.7 image.

Quick start
-----------

.. code-block:: python

    from vine_reduce.coffea import VineReduceCoffea
    from vine_reduce.taskvine_distributor import TaskVineDistributor
    from coffea_casa import CoffeaCasaVineWorkers

    # The manager must listen on port 8786: it's the only port workers
    # can reach your notebook on.
    distributor = TaskVineDistributor(port=8786,
                                      resources_processor={"cores": 1},
                                      resources_reducer={"cores": 1})
    workers = CoffeaCasaVineWorkers(distributor.manager, cores=4,
                                    memory_mb=8000, disk_mb=16000)
    workers.submit(10)

    vr = VineReduceCoffea(processors={"myanalysis": my_processor},
                          input=datasets, distributor=distributor,
                          results_dir="results")
    with distributor, workers:   # removes the workers when done
        vr.compute()

Without VineReduce, create the manager with ``coffea_casa.vine_manager()``,
which listens on port 8786 with TLS, and pass it to ``CoffeaCasaVineWorkers``
the same way.

Things to know
--------------

- **Dask or TaskVine, not both at once.** The TaskVine manager uses port
  8786, the same port as the Dask scheduler. Close any Dask cluster
  (``CoffeaCasaCluster`` or one started from the Dask sidebar) first;
  otherwise you get a "Port 8786 is already in use" error.
- **Security.** The manager must use TLS (``ssl=True``, the default for
  ``TaskVineDistributor``); workers always connect with TLS. Your bearer token
  is sent to the workers encrypted, so tasks can read data through XCache as
  Dask workers do. The notebook's environment variables are not copied into
  the jobs.
- **Software.** Tasks run in the worker image's Python environment, which
  matches the notebook image. To run in an environment of your own, use
  VineReduce's ``get_environment()`` and pass it to ``TaskVineDistributor(environment=...)``.
- **Idle workers** exit after ``idle_timeout`` seconds without work
  (default 900); ``workers.close()`` removes them right away.

Troubleshooting
---------------

``condor_q -constraint 'CoffeaCasaWorkerType == "taskvine"'`` lists TaskVine
worker jobs. If workers exit without connecting, ``workers.fetch_worker_logs()``
copies the stdout/stderr of finished workers into ``~/dask-worker-logs``
(``vine-worker-*.out`` / ``.err``) and returns their paths.
