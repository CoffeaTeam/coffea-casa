Deployment of Coffea-casa Analysis Facility at your Tier 2/Tier 3 grid site or Cluster
========================================================================================

This page describes the infrastructure requirements and deployment details for the
Coffea-Casa Analysis Facility.

Current Infrastructure @ T2 Nebraska
--------------------------------------

The production deployment at the University of Nebraska-Lincoln Tier 2 site runs on
the following stack:

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Component
     - Details
   * - **Operating System**
     - AlmaLinux 9.7
   * - **Kubernetes Version**
     - 1.34.5
   * - **GPU Resources**
     - 2× NVIDIA L40S
   * - **HTCondor Pool**
     - Nebraska Tier 2 (autoscales worker nodes on demand)
   * - **Storage**
     - XCache + EOS public (via XRootD redirector)

GPU Support
-----------

The facility is equipped with two NVIDIA L40S GPUs for accelerated computing workloads.
These are available to users who require GPU resources for their analyses. To request
access to GPU nodes, please open a `GitHub Discussion <https://github.com/CoffeaTeam/coffea-casa/discussions/categories/unl-tech-support>`_
or contact the facility administrators directly.

The L40S cards provide 48 GB of GDDR6 VRAM each and are well suited for machine
learning inference, histogram filling acceleration, and other GPU-aware HEP analysis
workflows.

Deploying Your Own Instance
----------------------------

To deploy Coffea-Casa at your own Tier 2 or Tier 3 grid site you will need:

* A Kubernetes cluster (tested on 1.34.5+)
* HTCondor for worker node scheduling
* Helm 3 for chart deployment
* An XCache or XRootD redirector for data access

The Helm chart and full configuration reference are maintained in the
`coffea-casa repository <https://github.com/CoffeaTeam/coffea-casa/tree/master/charts/coffea-casa>`_.
Refer to the ``values.yaml`` and ``values-prod.yaml`` files for a complete list of
configurable options.

.. note::
   A detailed step-by-step deployment guide is in progress. For now, please open a
   `GitHub issue <https://github.com/CoffeaTeam/coffea-casa/issues>`_ or reach out
   via the `e-group <mailto:coffea-casa-dev@cern.ch>`_ for deployment assistance.
