#!/bin/bash

set -x

if [[ "$SERVICEX_HOST" ]]; then
    touch $HOME/.servicex
    echo "Tokens: generating ServiceX config file (available only from Jupyterhub notebook)"
    echo "
api_endpoints:
  - name: uproot
    endpoint: $SERVICEX_HOST
    type: uproot
    " > $HOME/.servicex
fi

# Populating Dask configuration files (Dask is always enabled in the Helm charts)
sed -i -e "s|coffeateam/coffea-casa-analysis|${WORKER_IMAGE}|g" $DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml
sed -i -e "s|latest|${TAG}|g" $DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml
sed -i -e "s|/etc/cmsaf-secrets|${CERT_DIR}|g" $DASK_ROOT_CONFIG/dask.yaml
sed -i -e "s|CoffeaCasaCluster|${LABEXTENTION_FACTORY_CLASS}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|coffea_casa|${LABEXTENTION_FACTORY_MODULE}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|UNL HTCondor Cluster|${LABEXTENTION_CLUSTER}|g" $DASK_ROOT_CONFIG/labextension.yaml

# Both SKYHOOK_CEPH_KEYRING and SKYHOOK_CEPH_UUIDGEN are defined in Helm chart (not in a Docker image)
if [[ "$SKYHOOK_CEPH_KEYRING" && "$SKYHOOK_CEPH_UUIDGEN" ]]; then
  sed -i -e "s|%(SKYHOOK_CEPH_UUIDGEN)|${SKYHOOK_CEPH_UUIDGEN}|g" $CEPH_DIR/ceph.conf
  sed -i -e "s|%(SKYHOOK_CEPH_KEYRING)|${SKYHOOK_CEPH_KEYRING}|g" $CEPH_DIR/keyring
  # Testing ceph status
  ceph -s
fi

if [ "${LABEXTENTION_FACTORY_CLASS:-}" == "LocalCluster" ]; then
  # Used for testing purposes, CI and local development.
  echo "
distributed:
  version: 2
  dashboard:
    link: "/user/{JUPYTERHUB_USER}/proxy/{port}/status"
  " > $DASK_ROOT_CONFIG/dask.yaml
fi

# HTCondor scheduler settings
echo "CONDOR_HOST = ${CONDOR_HOST}" >> /opt/condor/config.d/schedd
echo "COLLECTOR_NAME = ${COLLECTOR_NAME}" >> /opt/condor/config.d/schedd
echo "UID_DOMAIN = ${UID_DOMAIN}" >> /opt/condor/config.d/schedd
echo "SCHEDD_HOST = ${SCHEDD_HOST}" >> /opt/condor/config.d/schedd

# Check environment
if [ -e "$HOME/environment.yml" ]; then
    echo "Conda: environment.yml found. Installing packages."
    /opt/conda/bin/conda env update -f $HOME/environment.yml
  elif [ -e "$HOME/environment.yaml" ]; then
    echo "Conda: environment.yaml found. Installing packages."
    /opt/conda/bin/conda env update -f $HOME/environment.yaml
  else
    echo "No environment.yml, conda will not install any package."
  fi

  if [ -e "$HOME/requirements.txt" ]; then
    echo "Pip: requirements.txt found. Installing packages."
    /opt/conda/bin/python -m pip install -r $HOME/requirements.txt
  else
    echo "No requirements.txt, pip will not install any module."
  fi

if [ "$EXTRA_CONDA_PACKAGES" ]; then
    echo "conda: EXTRA_CONDA_PACKAGES environment variable found.  Installing."
    /opt/conda/bin/conda install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "pip: EXTRA_PIP_PACKAGES environment variable found.  Installing".
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# Run extra commands
exec "$@"
