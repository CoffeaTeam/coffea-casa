.. _index:

.. py:currentmodule:: coffea_casa


Welcome to the Coffea-Casa Project!
==============================================================================================================


**Coffea-casa** is a prototype of an analysis facility that provides services for “low latency columnar analysis,” enabling rapid processing of data in a column-wise fashion.

Coffea-casa Analysis Facility (AF) services, based on *Dask* and *Jupyter Notebook* technologies, aim to dramatically lower time for analysis and provide an easily-scalable and user-friendly computational environment that will simplify, facilitate, and accelerate the delivery of HEP results.

.. image:: _static/coffea-casa-draft.png
   :alt: Prototype of Coffea-casa Analysis Facility
   :width: 100%
   :align: center

The facility is built on top of a Kubernetes cluster and integrates with dedicated resources, with resources allocated via fair share through the local HTCondor system and Nebraska Tier-2.


.. image:: _static/coffea-casa-resources.png
   :alt: Resources allocated for each user at Coffea-casa Analysis Facility
   :width: 100%
   :align: center

.. note::

    **Coffea-casa** is a prototype and is currently in active development: if you had noticed a bug or would like to leave us feedback,
    we invite you to open an issue directly on GitHub: <https://github.com/CoffeaTeam/coffea-casa/issues>


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Getting Started

   Why Dask? <https://docs.dask.org/en/latest/why.html>
   Dask-jobqueue introduction <https://jobqueue.dask.org/en/latest/howitworks.html>
   Dask-labextention introduction <https://pypi.org/project/dask-labextension/>
   Coffea Documentation <https://coffea-hep.readthedocs.io>


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: How To Use Coffea-casa

   cc_user.rst
   cc_user_ssl.rst
   cc_packages.rst
   cc_pocketcoffea.rst
   cc_tools.rst
   cc_metrics.rst
   cc_condor.rst
   cc_triton.rst
   cc_issues.rst

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Gallery of Coffea-casa Examples

   Coffea-Casa Template <gallery/coffea-casa-template>
   Single Top-Higgs Production (tHq) Analysis Tutorial <gallery/analysis_tutorial>
   Single Top-Higgs Production (tHq) Analysis <gallery/analysis-casa>
   ADL Benchmark 1 <gallery/example1>
   ADL Benchmark 2 <gallery/example2>
   ADL Benchmark 3 <gallery/example3>
   ADL Benchmark 4 <gallery/example4>
   ADL Benchmark 5 <gallery/example5>
   ADL Benchmark 6 <gallery/example6>
   ADL Benchmark 7 <gallery/example7>
   ADL Benchmark 8 <gallery/example8>
   Z-Peak Example <gallery/zpeak_example>
   Columnar Analysis with Coffea (AGC Tools 2022) <gallery/coffea_analysis>
   Coffea + Dask + ServiceX Example <gallery/ttbar_HT>


.. toctree::
  :maxdepth: 1
  :hidden:
  :caption: Deeper Look Into Coffea-Casa Internals

  cc_setup.rst
  cc_configuration.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Deploying Coffea-Casa at K8s Cluster

   cc_deployment.rst
   cc_local_deployment.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Detailed Information on Coffea-Casa

   cc_api.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Support & Help

   cc_support.rst
