Facility Usage Metrics
======================

This page is for facility operators. It defines a small set of metrics for how much, and how, a coffea-casa deployment is used, and shows where each one comes from. For measuring the performance of a single analysis, see :doc:`cc_metrics`.

All the metrics below come from data that Prometheus can scrape from a standard deployment. You don't need extra exporters, apart from kube-state-metrics, which ships with kube-prometheus-stack.

The metric set
--------------

.. list-table::
   :header-rows: 1
   :widths: 25 45 30

   * - Question
     - Metric
     - Source
   * - How many people have an account?
     - Registered users
     - JupyterHub
   * - How many people use it?
     - Users who had a server running in the last 24 hours, 7 days and 30 days
     - kube-state-metrics (or JupyterHub >= 3.1)
   * - Do people come back?
     - Ratio of 7-day to 30-day users
     - kube-state-metrics (or JupyterHub >= 3.1)
   * - Is it growing?
     - New users per week
     - JupyterHub
   * - How busy is it at peak?
     - Maximum number of running user servers per day
     - JupyterHub
   * - Does it work when people try it?
     - Share of successful spawns, and spawn time (90th percentile)
     - JupyterHub
   * - Which images do people pick?
     - Running user servers per image (flavour)
     - kube-state-metrics
   * - Do people scale out?
     - Users with Dask workers attached, and the total number of Dask workers
     - Dask scheduler
   * - What do people run?
     - Compute time per Dask task prefix
     - Dask scheduler

Scraping the hub
----------------

JupyterHub serves Prometheus metrics at ``/hub/metrics``. The hub Service that the chart creates already carries ``prometheus.io/*`` annotations, but the Prometheus Operator (and so kube-prometheus-stack) ignores those: it only scrapes targets that a ``ServiceMonitor`` selects. The chart can create one for you:

.. code-block:: yaml

    monitoring:
      serviceMonitor:
        enabled: true
        # Whatever your operator's serviceMonitorSelector matches
        labels:
          release: prometheus

The ``ServiceMonitor`` needs the ``monitoring.coreos.com`` CRDs to be installed, which is why it is disabled by default.

The hub only answers authenticated metrics requests unless you turn that off. Either create a hub API token with the ``read:metrics`` scope, store it in a Secret in the ``ServiceMonitor``'s namespace, and reference it:

.. code-block:: yaml

    monitoring:
      serviceMonitor:
        bearerTokenSecret:
          name: hub-metrics-token
          key: api_token

or allow unauthenticated scraping with ``jupyterhub.hub.authenticatePrometheus: false``. The metrics include no user names, but they are then readable by anything that can reach the hub.

If the hub's network policy is enabled (the z2jh default), also allow Prometheus to reach the hub on port 8081, for example:

.. code-block:: yaml

    jupyterhub:
      hub:
        networkPolicy:
          ingress:
            - from:
                - namespaceSelector:
                    matchLabels:
                      kubernetes.io/metadata.name: monitoring
              ports:
                - port: http

Queries
-------

The queries assume the default ``jupyterhub_`` metric prefix. Add a ``namespace="..."`` matcher to each selector if one Prometheus scrapes several deployments.

Restrict ``jupyterhub_*`` series to the hub's scrape job (``job="hub"``, after the hub Service). The Dask scheduler runs inside each user's Jupyter server, and the ``/metrics`` endpoint on its dashboard port also serves zero-valued ``jupyterhub_*`` series. Without the filter, those zeros end up in sums and averages.

JupyterHub
^^^^^^^^^^

.. code-block:: text

    # Registered users
    jupyterhub_total_users{job="hub"}

    # Active users (period is 24h, 7d or 30d); needs JupyterHub 3.1 or newer
    jupyterhub_active_users{job="hub", period="7d"}

    # New users per week (approximate: deleted users reduce it)
    delta(jupyterhub_total_users{job="hub"}[7d])

    # Peak concurrent user servers per day
    max_over_time(jupyterhub_running_servers{job="hub"}[1d])

    # Share of spawns that succeeded over the last day
      sum(increase(jupyterhub_server_spawn_duration_seconds_count{job="hub", status="success"}[1d]))
    / sum(increase(jupyterhub_server_spawn_duration_seconds_count{job="hub"}[1d]))

    # 90th percentile time to a running server
    histogram_quantile(0.9,
      sum by (le) (rate(jupyterhub_server_spawn_duration_seconds_bucket{job="hub", status="success"}[1d])))

Active users from user pods
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``jupyterhub_active_users`` only exists from JupyterHub 3.1 on. The same question can be answered for any hub version by counting the distinct user pods (named ``jupyter-<user>``) that kube-state-metrics has seen. This counts users who started a server, which is close to, but not the same as, JupyterHub's activity-based count:

.. code-block:: text

    # Users who had a server running in the last 7 days
    count(count by (pod) (max_over_time(kube_pod_info{pod=~"jupyter-.+"}[7d])))

    # Returning users: share of the last 30 days' users who also had a server this week
      count(count by (pod) (max_over_time(kube_pod_info{pod=~"jupyter-.+"}[7d])))
    / count(count by (pod) (max_over_time(kube_pod_info{pod=~"jupyter-.+"}[30d])))

The look-back can't be longer than your Prometheus retention.

Image flavours
^^^^^^^^^^^^^^

Each user server runs in a pod whose main container is called ``notebook``. kube-state-metrics reports its image:

.. code-block:: text

    count by (image) (kube_pod_container_info{container="notebook"})

To see which image each user picks, add ``jhub_user`` to kube-state-metrics' ``--metric-labels-allowlist`` (``pods=[jhub_user]``). The chart puts this label on every user pod, and ``kube_pod_labels`` then reports it as ``label_jhub_user``.

Dask
^^^^

The hub creates a ``dask-<user>`` Service with the label ``app: dask`` for each user. It exposes the scheduler's dashboard port (``dask-dashboard``, 8787), which also serves ``/metrics``. Scrape it with a ``ServiceMonitor`` such as:

.. code-block:: yaml

    apiVersion: monitoring.coreos.com/v1
    kind: ServiceMonitor
    metadata:
      name: dask-dashboard
    spec:
      selector:
        matchLabels:
          app: dask
      endpoints:
        - port: dask-dashboard
          path: /metrics
          interval: 30s

The ``service`` label on the scraped series then names the user. Useful queries:

.. code-block:: text

    # Users with at least one Dask worker
    count(dask_scheduler_workers > 0)

    # Dask workers across the facility
    sum(dask_scheduler_workers)

    # Compute time per task prefix over the last week, i.e. what people run
    topk(20, sum by (task_prefix_name) (increase(dask_scheduler_tasks_compute_seconds_total[7d])))

Grafana dashboard
-----------------

The chart ships a "Coffea-casa usage" Grafana dashboard with panels for all the queries above, plus spawns by result and servers per image over time. It has a data source selector, and a namespace selector for when one Prometheus scrapes several deployments. The user counts come from user pods (see above), so they work with any JupyterHub version; the "Active users" panel shows JupyterHub's own counts and stays empty before JupyterHub 3.1. Hub panels use the scrape job ``hub``; if yours differs, change the hidden ``hub_job`` dashboard variable. To install it, enable the ConfigMap that Grafana's dashboard sidecar picks up (the sidecar is on by default in kube-prometheus-stack):

.. code-block:: yaml

    monitoring:
      grafanaDashboard:
        enabled: true
        # Only needed if the sidecar watches a single namespace
        namespace: monitoring

The ConfigMap carries the ``grafana_dashboard: "1"`` label by default; change ``monitoring.grafanaDashboard.labels`` if your sidecar looks for another one.

Without the sidecar, or for a Grafana outside the cluster, import ``charts/coffea-casa/files/grafana/coffea-casa-usage.json`` from the coffea-casa repository through *Dashboards → New → Import*.

The image-flavour panels need kube-state-metrics, and the Dask panels need the Dask ``ServiceMonitor`` described above. Without them those panels stay empty.

Active time per user
--------------------

JupyterHub's ``active_users`` gauge counts people, not time. To report hours of active use, poll the hub's ``/hub/api/users`` endpoint periodically (for example from a CronJob with an admin API token) and add up the time during which each user's ``last_activity`` was recent. That is how coffea.casa produces its weekly usage summary.
