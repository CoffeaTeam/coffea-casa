.. _index:

.. py:currentmodule:: coffea_casa


Welcome to Coffea-casa project!
==============================================================================================================


Coffea-casa is a prototype of a U.S. CMS analysis facility that provides services for “low latency columnar analysis”, enabling rapid processing of data in a column-wise fashion.

Coffea-casa Analysis Facility (AF) services, based on Dask and Jupyter notebooks technologies, aim to dramatically lower time for analysis and provide an easily-scalable and user-friendly computational environment that will simplify, facilitate, and accelerate the delivery of HEP results.

.. image:: _static/coffea-casa-draft.png
   :alt: Prototype of Coffea-casa Analysis Facility @ T2 Nebraska
   :width: 100%
   :align: center

The facility is built on top of a Kubernetes cluster and integrates with dedicated resources with resources allocated via fair share through the local HTCondor system and Nebraska Tier-2 resources.


.. image:: _static/coffea-casa-resources.png
   :alt: Resources allocated for each user at Coffea-casa Analysis Facility @ T2 Nebraska
   :width: 100%
   :align: center

.. note::

    ``Coffea-casa is`` a prototype and currently is actively developing: if you had noticed a bug or would like to leave us a feedback,
    we invite you to open an issue directly in GH: <https://github.com/CoffeaTeam/coffea-casa/issues>


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Getting Started

   cc_setup.rst
   cc_support.rst
   Why Dask? <https://docs.dask.org/en/latest/why.html>
   Dask-jobqueue introduction <https://jobqueue.dask.org/en/latest/howitworks.html>
   Dask-labextention introduction <https://pypi.org/project/dask-labextension/>


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: How To Use ``Coffea-casa``
   Coffea documentation <https://coffeateam.github.io/coffea/>
   cc_user.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Gallery of ``Coffea-casa`` Examples

   ADL benchmark 1 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example1.ipynb>
   ADL benchmark 2 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example2.ipynb>
   ADL benchmark 3 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example3.ipynb>
   ADL benchmark 4 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example4.ipynb>
   ADL benchmark 5 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example5.ipynb>
   ADL benchmark 6 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example6.ipynb>
   ADL benchmark 7 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example7.ipynb>
   ADL benchmark 8 <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/benchmarks/example8.ipynb>
   Single top-Higgs production (tHq) analysis <https://github.com/CoffeaTeam/coffea-casa-tutorials/blob/master/analysis-casa.ipynb>


.. toctree::
  :maxdepth: 1
  :hidden:
  :caption: For Developer - Deeper Look Into ``Coffea-casa`` Internals

  cc_configuration.rst

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: For Developer - Deploying ``Coffea-casa`` at Kubernetes Cluster

   cc_deployment.rst
   cc_setup.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: For Developer - Detailed Information on the Python API ``Coffea_casa``

   cc_api.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Support & Help

   cc_support.rst
