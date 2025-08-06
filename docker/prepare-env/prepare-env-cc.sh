#!/bin/bash

set -x

# Enable Bash Git completions
if [ -f /usr/share/bash-completion/completions/git ]; then
    . /usr/share/bash-completion/completions/git
fi

if [[ "$SERVICEX_HOST" ]] && [[ "$SERVICEX_TYPE" ]]; then
    touch $HOME/.servicex
    echo "Tokens: generating ServiceX config file (available only from Jupyterhub notebook)"
    echo "
api_endpoints:
  - name: $SERVICEX_TYPE
    endpoint: $SERVICEX_HOST
    type: $SERVICEX_TYPE
    " > $HOME/.servicex
fi

# Populating Dask configuration files
sed -i -e "s|hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu|${WORKER_IMAGE}|g" $DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml
sed -i -e "s|development|${TAG}|g" $DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml
sed -i -e "s|/etc/cmsaf-secrets|${CERT_DIR}|g" $DASK_ROOT_CONFIG/dask_tls.yaml
sed -i -e "s|LocalCluster|${LABEXTENTION_FACTORY_CLASS}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|dask.distributed|${LABEXTENTION_FACTORY_MODULE}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|Local Cluster|${LABEXTENTION_CLUSTER}|g" $DASK_ROOT_CONFIG/labextension.yaml

if [ "${LABEXTENTION_FACTORY_CLASS:-}" == "LocalCluster" ]; then
  # FIXME: for now no need to have cartificates
  sed -i -e "s|require-encryption: True|require-encryption: False|g" $DASK_ROOT_CONFIG/dask_tls.yaml
fi

# HTCondor scheduler settings
echo "CONDOR_HOST = ${CONDOR_HOST}" >> /opt/condor/config.d/schedd
echo "COLLECTOR_NAME = ${COLLECTOR_NAME}" >> /opt/condor/config.d/schedd
echo "UID_DOMAIN = ${UID_DOMAIN}" >> /opt/condor/config.d/schedd
echo "SCHEDD_HOST = ${SCHEDD_HOST}" >> /opt/condor/config.d/schedd
echo "DELEGATE_JOB_GSI_CREDENTIALS = FALSE" >> /opt/condor/config.d/schedd

# Values should be defined in Helm chart (not in a Docker image)
if [[ "$SKYHOOK_CEPH_KEYRING" && "$SKYHOOK_CEPH_UUIDGEN" && "$SKYHOOK_CLUSTER_ADDR" && "$SKYHOOK_PUBLIC_ADDR" && "$SKYHOOK_MON_HOST" ]]; then
  sed -i -e "s|%(SKYHOOK_CEPH_UUIDGEN)|${SKYHOOK_CEPH_UUIDGEN}|g" $CEPH_DIR/ceph.conf
  sed -i -e "s|%(SKYHOOK_CEPH_KEYRING)|${SKYHOOK_CEPH_KEYRING}|g" $CEPH_DIR/keyring
  sed -i -e "s|%(SKYHOOK_MON_HOST)|${SKYHOOK_MON_HOST}|g" $CEPH_DIR/ceph.conf
  sed -i -e "s|%(SKYHOOK_PUBLIC_ADDR)|${SKYHOOK_PUBLIC_ADDR}|g" $CEPH_DIR/ceph.conf
  sed -i -e "s|%(SKYHOOK_CLUSTER_ADDR)|${SKYHOOK_CLUSTER_ADDR}|g" $CEPH_DIR/ceph.conf
  # Testing ceph status
  #ceph -s
else
  echo "Skyhook was not configured. Please add next env values: SKYHOOK_CEPH_KEYRING SKYHOOK_CEPH_UUIDGEN SKYHOOK_CLUSTER_ADDR SKYHOOK_PUBLIC_ADDR SKYHOOK_MON_HOST in helm charts."
fi

# Check environment
if [ -e "$HOME/environment.yml" ]; then
    echo "Conda: environment.yml found. Installing packages."
    /opt/conda/bin/mamba env update -f $HOME/environment.yml
  elif [ -e "$HOME/environment.yaml" ]; then
    echo "Conda: environment.yaml found. Installing packages."
    /opt/conda/bin/mamba env update -f $HOME/environment.yaml
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
    /opt/conda/bin/mamba install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "pip: EXTRA_PIP_PACKAGES environment variable found.  Installing".
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# Run extra commands
#exec "/usr/local/bin/prepare-env.sh" "$@"
exec "$@"
