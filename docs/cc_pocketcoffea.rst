Running PocketCoffea
====================

`PocketCoffea <https://pocketcoffea.readthedocs.io>`_ is an analysis framework built on coffea 0.7. It runs on coffea-casa with its ``dask@casa`` executor, which starts a :class:`CoffeaCasaCluster` with HTCondor workers for each run.

PocketCoffea needs coffea 0.7 and awkward 1, while the coffea-casa images ship current coffea. You therefore install PocketCoffea in a conda environment of your own, and coffea-casa ships that environment to the workers (see :doc:`cc_packages`). This works from any coffea-casa image flavour.

1. Create a PocketCoffea environment
------------------------------------
Run this once in a terminal. Creating the environment takes a few minutes:

.. code-block:: bash

    mamba create -y -p ~/.conda/envs/pocketcoffea -c conda-forge python=3.11 conda-pack xrootd "setuptools<71" "pyarrow<26"
    ~/.conda/envs/pocketcoffea/bin/python -m pip install "git+https://github.com/PocketCoffea/PocketCoffea@main" coffea-casa

.. note::

    The ``dask@casa`` executor described here is in PocketCoffea's ``main`` branch and will be part of its next release (after 0.9.13). Until then, install PocketCoffea from GitHub as above; afterwards, ``pip install pocket-coffea coffea-casa`` is enough.

The version limits avoid known problems:

* ``setuptools<71``: PocketCoffea requires it. Installing it with conda, rather than letting pip replace conda's version later, keeps the environment packable for the workers.
* ``pyarrow<26``: pyarrow 26 requires NumPy 2, but coffea 0.7 needs NumPy 1.

You don't need to activate the environment: running its ``pocket-coffea`` by full path, as below, is enough for coffea-casa to ship it to the workers.

2. Point your datasets at files the facility can read
-----------------------------------------------------
Workers read the files listed in your dataset definitions directly, so use paths that work at your facility. On instances with XCache, replace the redirector in the file paths with ``xcache``, for example:

.. code-block:: bash

    sed -i 's#root://cmsxrootd.fnal.gov/#root://xcache/#' datasets/my_datasets.json

See :doc:`cc_user` for how data access works at each coffea-casa instance.

3. Run the analysis
-------------------
From your analysis directory:

.. code-block:: bash

    ~/.conda/envs/pocketcoffea/bin/pocket-coffea run --cfg config.py -o output --executor dask@casa --scaleout 10

For a quick test, add ``--limit-files 1 --limit-chunks 2``.

The first run packs the environment, which takes a few minutes and prints ``Packed ...``. Workers then download and unpack it before they start, so the progress bar may stay at 0% for a few minutes. Later runs reuse the packed environment until you change it.

The ``dask@casa`` executor understands these run options, set in a file passed with ``--custom-run-options`` or, where available, as command-line flags:

``scaleout`` (``--scaleout``, default 10)
    Number of workers. With ``adaptive: true``, the maximum number of workers.

``adaptive`` (default ``false``)
    Scale the number of workers with the amount of work, between 1 and ``scaleout``.

``cores-per-worker`` / ``mem-per-worker`` (default 1 / ``"4GB"``)
    Resources of each worker.

``scheduler-address`` (default none)
    Use an already running Dask cluster instead of starting one. You can also set ``DASK_SCHEDULER_ADDRESS``. That cluster's workers must have PocketCoffea, for example a :class:`CoffeaCasaCluster` created from a notebook running in your PocketCoffea environment. Clusters started from the Dask sidebar use the image's environment and won't work.

For example, to run adaptively on up to 50 workers with more memory each:

.. code-block:: yaml

    # my_run_options.yaml
    scaleout: 50
    adaptive: true
    mem-per-worker: "8GB"

.. note::

    Don't call ``client.restart()`` on coffea-casa clusters. Restarting removes the HTCondor workers instead of restarting them, and the cluster is left without workers. To get fresh workers, close the cluster and start a new one.

Building datasets
-----------------
PocketCoffea's dataset tools (``pocket-coffea build-datasets``) query CMS data-management services that aren't available from coffea-casa. Build your dataset definition files where you normally do, for example on lxplus, and copy the resulting JSON files to coffea-casa.

Troubleshooting
---------------
**Where are the worker logs?** While a worker is running:

.. code-block:: bash

    condor_q -constraint 'CoffeaCasaClusterId =!= undefined && JobStatus != 4' -af ClusterId JobStatus
    condor_tail -stderr -maxbytes 10000000 <ClusterId>.0

After workers have finished, ``condor_transfer_data <ClusterId>`` copies their logs into ``~/dask-worker-logs/``. Logs of workers removed when the cluster closes are lost, so collect them while the run is still going.

``Files managed by conda were found to have been deleted/overwritten``
    pip replaced a package that conda installed, and the environment can't be packed. Install that package's required version with conda, e.g. ``mamba install -p ~/.conda/envs/pocketcoffea "setuptools<71"``, or recreate the environment as in step 1.

``pyarrow requires NumPy 2.0 or newer``
    Install ``pyarrow<26`` in the environment.

``Access denied`` or ``file not found`` when opening files
    The workers can't read that path. Check that your dataset definitions use the facility's data access (step 2).
