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
   Coffea Documentation <https://coffeateam.github.io/coffea/>


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: How To Use Coffea-casa

   cc_user.rst
   cc_user_ssl.rst
   cc_examples.ipynb
   cc_packages.rst
   cc_metrics.rst
   cc_condor.rst
   cc_issues.rst

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Gallery of Coffea-casa Examples

   gallery/coffea-casa-template.ipynb
   gallery/example1.ipynb
   gallery/example2.ipynb
   gallery/example3.ipynb
   gallery/example4.ipynb
   gallery/example5.ipynb
   gallery/example6.ipynb
   gallery/example7.ipynb
   gallery/example8.ipynb
   gallery/analysis_tutorial.ipynb
   gallery/analysis-casa.ipynb


.. toctree::
  :maxdepth: 1
  :hidden:
  :caption: Deeper Look Into ``Coffea-Casa`` Internals

  cc_setup.rst
  cc_configuration.rst


.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Deploying Coffea-Casa at K8s Cluster

   cc_deployment.rst


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
