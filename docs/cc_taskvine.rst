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
  otherwise you get a "Port 8786 is already in use" error. The same error
  appears when a manager from an earlier run is still alive, in this kernel
  or in another notebook's: restart or shut down that kernel.
- **Workers connect only while the manager waits.** The manager accepts
  workers and hands out tasks only inside ``m.wait()`` (VineReduce's
  ``compute()`` does this for you). A notebook that submits tasks and then
  stops calling ``wait()`` sees no workers connect.
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

Checking that it works
----------------------

This runs a few small tasks on two workers. It checks that workers reach your
notebook, that files move between workers, and that a worker can read CMS data
through XCache. Run it in a fresh kernel:

.. code-block:: python

    import ndcctools.taskvine as vine
    from coffea_casa import CoffeaCasaVineWorkers, vine_manager

    m = vine_manager()
    workers = CoffeaCasaVineWorkers(m, cores=1, memory_mb=2000, disk_mb=4000)
    workers.submit(2)

    f = m.declare_temp()
    producer = vine.Task("python -c 'print(41 + 1)' > out.txt")
    producer.add_output(f, "out.txt")
    m.submit(producer)
    for _ in range(8):
        t = vine.Task("cat in.txt; hostname")
        t.add_input(f, "in.txt")
        m.submit(t)
    url = "root://xcache//store/data/Run2018A/DoubleMuon/NANOAOD/02Apr2020-v1/30000/0555868D-6B32-D249-9ED1-6B9A6AABDAF7.root"
    m.submit(vine.Task(f"""python -c "import uproot; print(uproot.open('{url}')['Events'].num_entries)" """))

    while not m.empty():          # the first tasks wait for workers to start
        t = m.wait(10)
        if t:
            print(t.id, t.successful(), t.output.strip().replace("\n", " | "))
    workers.close()

Every task should print ``True``. The ``cat`` tasks print ``42`` and the
host name of one of the two workers, and the last task prints an event count.
The facility's daily smoke tests run the same checks
(`taskvine/taskvine-smoke.ipynb
<https://github.com/CoffeaTeam/coffea-casa-smoke/tree/main/taskvine>`_).

Troubleshooting
---------------

``condor_q -constraint 'CoffeaCasaWorkerType == "taskvine"'`` lists TaskVine
worker jobs. If workers exit without connecting, ``workers.fetch_worker_logs()``
copies the stdout/stderr of finished workers into ``~/dask-worker-logs``
(``vine-worker-*.out`` / ``.err``) and returns their paths.
