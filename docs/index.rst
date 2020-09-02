.. _index:

.. py:currentmodule:: coffea_casa


coffea-casa
==============================================================================================================


A Prototype U.S. CMS analysis facility for Columnar Object Framework For Effective Analysis,
provides services for “low latency columnar analysis”,
enabling rapid processing of data in a column-wise fashion.

Coffea-casa Analysis Facility (AF) services, based on Dask and Jupyter notebooks,
aim to dramatically lower time for analysis and provide an easily-scalable
and user-friendly computational environment that will simplify, facilitate,
and accelerate the delivery of HEP results.

The facility is built on top of a Kubernetes cluster and integrates dedicated resources
with resources allocated via fairshare through the local HTCondor system.


.. note::

    ``Coffea-casa is`` a prototype: please if you had noticed a bug,
    we invite you to open an issue directly in GH: <https://github.com/CoffeaTeam/coffea-casa/>



:doc:`setup`
    How to setup ``coffea-casa`` JH notebook.



:doc:`configuration`
    Configuration of ``coffea-casa`` AF together with Dask JupyterLab extension.



:doc:`api`
  Detailed information on the Python API ``coffea_casa`` module.


.. toctree::
   :maxdepth: 2
   :hidden:

   self

.. toctree::
   :maxdepth: 2
   :hidden:

   setup

.. toctree::
   :maxdepth: 2
   :hidden:

   configuration

.. toctree::
   :maxdepth: 2
   :hidden:

   api
