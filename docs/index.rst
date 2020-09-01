coffea-casa - A Prototype U.S. CMS analysis facility for Columnar Object Framework For Effective Analysis
==============================================================================================================

.. py:currentmodule:: coffea_casa


The prototype analysis facility provides services for “low latency columnar analysis”,
enabling rapid processing of data in a column-wise fashion.
``Coffea-casa Analysis Facility (AF)`` services, based on Dask and Jupyter notebooks,
aim to dramatically lower time for analysis and provide an easily-scalable
and user-friendly computational environment that will simplify, facilitate,
and accelerate the delivery of HEP results.
The facility is built on top of a Kubernetes cluster and integrates dedicated resources
with resources allocated via fairshare through the local HTCondor system.


.. note::

    ``Coffea-casa is`` still a prototype software. Please if you had noticed a bug,
    we invite you to open an issue directly in GH issues: <https://github.com/CoffeaTeam/coffea-casa/>

How to start to work with ``coffea-casa``:


:doc:`setup`
    How to setup ``coffea-casa`` JH notebook.


:doc:`adl1`
    A brief examples Jupyter notebook, using :class:`CoffeaCasaCluster`


:doc:`coffea_xcache`
    A brief examples Jupyter notebook using XCache, using :class:`CoffeaCasaCluster`


Configuration of ``coffea-casa`` AF together with Dask JupyterLab extension:


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
   adl1
   coffea_xcache

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: How to configure Dask Labextension cluster

   configuration

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: ``coffea_casa`` module API

   api
