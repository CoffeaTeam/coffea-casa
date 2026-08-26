Deploying Coffea-Casa Locally (k3d / minikube)
================================================

This page covers running the ``charts/coffea-casa`` Helm chart on a local
Kubernetes cluster, for testing chart changes before opening a pull request.
It is not a production deployment guide - see
:doc:`cc_deployment` for that.

Both sets of instructions below were verified end-to-end against this
repository's current chart (``jupyterhub`` dependency ``4.4.1``).

Pick whichever local cluster tool you prefer:

* **k3d** - k3s running in Docker. Fast to start, low resource use.
* **minikube** - its own VM/driver. Heavier, closer to a "real" cluster.

The deployment steps are identical either way once the cluster is up - only
cluster creation differs.

Prerequisites
-------------

* Docker (or another container runtime your chosen tool supports)
* `kubectl <https://kubernetes.io/docs/tasks/tools/#kubectl>`_
* `Helm <https://helm.sh/docs/intro/install/>`_ 3 or newer
* Either `k3d <https://k3d.io/#installation>`_ or
  `minikube <https://minikube.sigs.k8s.io/docs/start/>`_

1. Create a cluster
--------------------

k3d
~~~

.. code-block:: sh

   k3d cluster create coffea-casa-dev --wait

minikube
~~~~~~~~

.. code-block:: sh

   minikube start

``kubectl`` picks up whichever cluster you just created automatically
(check with ``kubectl config current-context``). If you have other clusters
configured, make sure the context is ``k3d-coffea-casa-dev`` or
``minikube`` before continuing - ``kubectl config use-context <name>`` to
switch.

2. Deploy the chart
--------------------

From the repository root:

.. code-block:: sh

   cd charts/coffea-casa
   helm dependency update
   kubectl create namespace coffea-casa
   helm upgrade --install coffea-casa . \
     -f values.yaml \
     --namespace coffea-casa \
     --wait --timeout 10m

``values.yaml`` is the chart's own local/dev profile: dummy authentication
(any username/password is accepted), no TLS, a NodePort proxy, and a single
test ``singleuser`` profile - it's meant for exactly this, not for a real
deployment. ``values-prod.yaml`` and ``values-cmsaf-prod.yaml`` are real
site configs and need real secrets/hostnames you won't have locally.

.. note::
   **Apple Silicon / Docker Desktop:** if the ``hub`` pod goes into
   ``CrashLoopBackOff`` with exit code 132 and no useful log output (or
   logs stop right after a ``pip install`` step), this is **not a chart
   bug** - it's the ``cryptography`` package's OpenSSL backend hitting a
   CPU-feature-detection bug under Docker Desktop's arm64 VM, specifically
   when generating an RSA key (JupyterHub does this during startup for TLS
   cert self-signing). It reproduces identically on both k3d and minikube,
   since the cause is the underlying Docker Desktop VM, not the cluster
   tool.

   Work around it by forcing OpenSSL to skip ARM crypto-extension
   detection:

   .. code-block:: sh

      helm upgrade --install coffea-casa . \
        -f values.yaml \
        --set-string jupyterhub.hub.extraEnv.OPENSSL_armcap=0 \
        --namespace coffea-casa \
        --wait --timeout 10m

   This is a local-machine workaround only - don't add it to any committed
   values file; it isn't needed on Linux CI runners or Intel Macs.

3. Access JupyterHub
---------------------

.. code-block:: sh

   kubectl port-forward svc/proxy-public 8080:80 -n coffea-casa

Then open http://localhost:8080. Neither k3d's nor minikube's Docker
driver reliably exposes NodePorts straight to the host on macOS, so
port-forward is the simplest option regardless of which tool you're using.

Log in with **any username and any password** - ``values.yaml`` configures
JupyterHub's ``DummyAuthenticator``, which accepts anything.

4. Spawning a notebook
------------------------

``values.yaml``'s default profile points at a real published image
(``hub.opensciencegrid.org/coffea-casa/cc-dask-alma9:development``). Two
things worth knowing before you click "Start":

* **That image is amd64-only.** On an Apple Silicon Mac (arm64), spawning
  will fail with ``ImagePullBackOff: no matching manifest for
  linux/arm64/v8`` - this is expected, not a chart problem. It works as-is
  on amd64 hosts (Linux CI runners, Intel Macs).
* To test against an image you built locally instead (e.g. while iterating
  on ``docker/Dockerfile.cc-dask-alma9``), build it, load it into your
  cluster (``k3d image import <tag> -c coffea-casa-dev``, or ``minikube
  image load <tag>``), and point the chart at it with an overlay values
  file overriding ``jupyterhub.singleuser.profileList`` -
  ``ci/values-chart-ci.yaml`` is exactly this, used by
  ``.github/workflows/chart-test.yaml``'s CI spawn test, and works as a
  local example too:

  .. code-block:: sh

     helm upgrade --install coffea-casa . \
       -f values.yaml \
       -f ../../ci/values-chart-ci.yaml \
       --set-string jupyterhub.hub.extraEnv.OPENSSL_armcap=0 \
       --namespace coffea-casa \
       --wait --timeout 10m

5. Cleaning up
---------------

.. code-block:: sh

   kubectl delete namespace coffea-casa

   # k3d
   k3d cluster delete coffea-casa-dev

   # minikube
   minikube delete
