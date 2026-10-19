Running PocketCoffea
====================

`PocketCoffea <https://pocketcoffea.readthedocs.io>`_ is a CMS analysis framework built on coffea 0.7. It runs on coffea-casa with its ``dask@casa`` executor, which starts a :class:`CoffeaCasaCluster` with HTCondor workers for each run.

PocketCoffea needs coffea 0.7 and awkward 1, while the coffea-casa images ship current coffea. You therefore install PocketCoffea in a conda environment of your own, and coffea-casa ships that environment to the workers (see :doc:`cc_packages`). This works from any coffea-casa image flavour.

1. Create a PocketCoffea environment
------------------------------------
Run this once in a terminal. Creating the environment takes a few minutes:

.. code-block:: bash

    mamba create -y -p ~/.conda/envs/pocketcoffea -c conda-forge python=3.11 conda-pack "xrootd=6.1.0" "setuptools<71" "pyarrow<26"
    ~/.conda/envs/pocketcoffea/bin/python -m pip install pocket-coffea coffea-casa

The version limits avoid known problems:

* ``setuptools<71``: PocketCoffea requires it. Installing it with conda, rather than letting pip replace conda's version later, keeps the environment packable for the workers.
* ``pyarrow<26``: pyarrow 26 requires NumPy 2, but coffea 0.7 needs NumPy 1.
* ``xrootd=6.1.0``: with XRootD 6.2.0, reading files from some sites with a grid proxy fails (``secgsi ... refuse to sign`` followed by ``Access denied``).

You don't need to activate the environment: running its ``pocket-coffea`` by full path, as below, is enough for coffea-casa to ship it to the workers.

2. Choose how to read the data
------------------------------
**With coffea-casa tokens (CMS instance).** No grid certificate is needed. Read files through XCache by using the ``xcache`` redirector in your dataset definitions, for example:

.. code-block:: bash

    sed -i 's#root://xrootd-cms.infn.it/#root://xcache/#' datasets/my_datasets.json

See :doc:`cc_user` for more on XCache.

**With a grid proxy.** This is needed to read through other redirectors, and on instances without CMS tokens. coffea-casa images don't include the VOMS tools, so create the proxy elsewhere, for example on lxplus:

.. code-block:: bash

    voms-proxy-init -voms cms -rfc --valid 168:0
    cat $(voms-proxy-info -path)

Copy the printed proxy, from the first ``-----BEGIN`` line to the last ``-----END`` line. Then save it on coffea-casa: run ``cat > ~/x509up_cms`` in a terminal, paste, press Enter and then Ctrl+D. Make the file readable only by you, and tell PocketCoffea where it is:

.. code-block:: bash

    chmod 600 ~/x509up_cms
    echo "voms-proxy: $HOME/x509up_cms" > my_run_options.yaml

The executor exports the proxy as ``X509_USER_PROXY`` before starting the cluster, and HTCondor then sends it to every worker. Without a proxy, the executor prints ``No usable VOMS proxy`` and continues with tokens. The proxy is your grid credential: delete it when you no longer need it.

3. Run the analysis
-------------------
From your analysis directory:

.. code-block:: bash

    ~/.conda/envs/pocketcoffea/bin/pocket-coffea run --cfg config.py -o output --executor dask@casa --scaleout 10

Add ``--custom-run-options my_run_options.yaml`` if you created one in the previous step, and ``--limit-files 1 --limit-chunks 2`` for a quick test.

The first run packs the environment, which takes a few minutes and prints ``Packed ...``. Workers then download and unpack it before they start, so the progress bar may stay at 0% for a few minutes. Later runs reuse the packed environment until you change it.

The ``dask@casa`` executor understands these run options, either in a run options file or, where available, as command-line flags:

``scaleout`` (``--scaleout``, default 10)
    Number of workers. With ``adaptive: true``, the maximum number of workers.

``adaptive`` (default ``false``)
    Scale the number of workers with the amount of work, between 1 and ``scaleout``.

``cores-per-worker`` / ``mem-per-worker`` (default 1 / ``"4GB"``)
    Resources of each worker.

``scheduler-address`` (default none)
    Use an already running Dask cluster instead of starting one. You can also set ``DASK_SCHEDULER_ADDRESS``. That cluster's workers must have PocketCoffea, for example a :class:`CoffeaCasaCluster` created from a notebook running in your PocketCoffea environment. Clusters started from the Dask sidebar use the image's environment and won't work.

``voms-proxy`` / ``ignore-grid-certificate``
    Path to a grid proxy, or ``true`` to never look for one.

.. note::

    Don't call ``client.restart()`` on coffea-casa clusters. Restarting removes the HTCondor workers instead of restarting them, and the cluster is left without workers. To get fresh workers, close the cluster and start a new one.

Building datasets
-----------------
PocketCoffea's dataset tools (``pocket-coffea build-datasets``) query DAS and Rucio with a grid proxy only. Build your dataset definition files where you have a proxy and the CMS tools, for example on lxplus, and copy the resulting JSON files to coffea-casa.

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

``Access denied`` when opening files
    The site the redirector chose didn't accept your credentials. Check that the proxy is valid and that the environment uses ``xrootd=6.1.0``, or use another redirector such as ``root://cmsxrootd.fnal.gov/``.

``excessive access rights`` in a worker log
    The proxy file is readable by others. Run ``chmod 600`` on it.
