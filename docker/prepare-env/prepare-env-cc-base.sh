#!/bin/bash

set -x

# Populating Dask configuration files
sed -i -e "s|LocalCluster|${LABEXTENTION_FACTORY_CLASS}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|dask.distributed|${LABEXTENTION_FACTORY_MODULE}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|Local Cluster|${LABEXTENTION_CLUSTER}|g" $DASK_ROOT_CONFIG/labextension.yaml

# HTCondor scheduler settings
echo "CONDOR_HOST = ${CONDOR_HOST}" >> /opt/condor/config.d/schedd
echo "COLLECTOR_NAME = ${COLLECTOR_NAME}" >> /opt/condor/config.d/schedd
echo "UID_DOMAIN = ${UID_DOMAIN}" >> /opt/condor/config.d/schedd
echo "SCHEDD_HOST = ${SCHEDD_HOST}" >> /opt/condor/config.d/schedd

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
exec "$@"
