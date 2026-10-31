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

Authentication
--------------

The chart ships two OAuth authenticators in ``files/hub-extra/`` (packaged into
the ``hub-extra-config-d`` ConfigMap) for the z2jh 4.x hub image
(Python 3.12, oauthenticator 17.x). Both are opt-in: mount them with
``jupyterhub.hub.extraVolumeMounts`` as shown (commented out) in ``values.yaml``.

``oauthenticator.coffea.CoffeaOAuthenticator``
   A ``GenericOAuthenticator`` that copies the user's OAuth ``access_token`` into
   the ``jupyter-<user>`` Kubernetes secret mounted at ``/etc/cmsaf-secrets``,
   where it is used for token-based data access (e.g. XCache). On every token
   refresh (every ``Authenticator.auth_refresh_age`` seconds) it exchanges the
   ``refresh_token`` for a new ``access_token``, so the token in the secret stays
   valid. Set ``CoffeaOAuthenticator.always_refresh_tokens: false`` for the
   upstream behaviour (refresh only once the provider rejects the current token).
   The provider must issue refresh tokens: request the ``offline_access`` scope
   and enable refresh tokens on the OAuth client.

``coffea_multiauthenticator.CoffeaMultiAuthenticator``
   Several login routes on one hub, e.g. CILogon at ``/hub/cilogon`` and CMS IAM
   at ``/hub/cms``. It extends
   `jupyterhub-multiauthenticator <https://github.com/idiap/multiauthenticator>`_
   (pip-install ``jupyterhub-multiauthenticator==0.4.0`` in ``hub.args``) so that
   token refresh is handed to the route the user logged in with. Users who logged
   in before it was enabled have to log in once more. A ``client_secret`` written
   as ``ENV_<NAME>`` is read from the hub environment variable ``<NAME>``.

Example (secrets from a ``hub-oidc`` Kubernetes secret):

.. code-block:: yaml

   jupyterhub:
     hub:
       args:
         - pip install --cache-dir /srv/jupyterhub/.cache/pip pyjwt
             jupyterhub-multiauthenticator==0.4.0
           && jupyterhub --config /usr/local/etc/jupyterhub/jupyterhub_config.py --upgrade-db
       extraEnv:
         HUB_AUTH_CILOGON_CLIENT_SECRET:
           valueFrom: {secretKeyRef: {name: hub-oidc, key: cilogon_client_secret}}
         HUB_AUTH_CMS_CLIENT_SECRET:
           valueFrom: {secretKeyRef: {name: hub-oidc, key: cms_client_secret}}
       config:
         Authenticator:
           enable_auth_state: true
           auth_refresh_age: 1800
         JupyterHub:
           authenticator_class: coffea_multiauthenticator.CoffeaMultiAuthenticator
         MultiAuthenticator:
           # Same username from either route, so users keep one home directory
           username_prefix: ""
           authenticators:
             - authenticator_class: cilogon
               url_prefix: /cilogon
               config:
                 client_id: cilogon:/client_id/<id>
                 client_secret: ENV_HUB_AUTH_CILOGON_CLIENT_SECRET
                 oauth_callback_url: https://<hub>/hub/cilogon/oauth_callback
                 # allowed_idps, allowed_groups, ...
             - authenticator_class: oauthenticator.coffea.CoffeaOAuthenticator
               url_prefix: /cms
               config:
                 login_service: CMS IAM  # login button label
                 client_id: <id>
                 client_secret: ENV_HUB_AUTH_CMS_CLIENT_SECRET
                 oauth_callback_url: https://<hub>/hub/cms/oauth_callback
                 authorize_url: https://cms-auth.cern.ch/authorize
                 token_url: https://cms-auth.cern.ch/token
                 userdata_url: https://cms-auth.cern.ch/userinfo
                 username_claim: email
                 allow_all: true
                 scope: [openid, profile, email, offline_access, "storage.read:/"]

.. note::
   oauthenticator 16+ denies every user unless ``allow_all``,
   ``allowed_users`` or ``allowed_groups`` is set for the authenticator.
