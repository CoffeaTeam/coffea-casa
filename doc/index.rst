Coffea-Casa
=========

.. py:currentmodule:: coffea_casa


The prototype analysis facility provides services for “low latency columnar analysis”,
enabling rapid processing of data in a column-wise fashion.
Coffea-casa Analysis Facility (AF) services, based on Dask and Jupyter notebooks,
aim to dramatically lower time for analysis and provide an easily-scalable
and user-friendly computational environment that will simplify, facilitate,
and accelerate the delivery of HEP results.
The facility is built on top of a Kubernetes cluster and integrates dedicated resources
with resources allocated via fairshare through the local HTCondor system.


.. note::

    Coffea-casa is still a prototype software. Please if you had noticed a bug,
    we invite you to open an issue directly in GH issues: <https://github.com/CoffeaTeam/coffea-casa/>

How to start to work with Coffea-casa:

:doc:`installation`
    How to setup Coffea-casa JH notebook.


:doc:`examples`
    A brief examples Jupyter notebooks,using :class:`CoffeaCasaCluster`


Configuration of Coffea-casa AF together with JupyterLab extension:


:doc:`configuration`
    Information on using Dask JupyterLab extension.


Detailed information on the Python API:

:doc:`api`
    API documentation for ``coffea_casa``.


.. toctree::
   :maxdepth: 2
   :hidden:

   self

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Quick Start

   setup
   examples

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: How to configure

   configuration

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: ``coffea_casa`` API

   api
