#!/bin/bash

set -x

# Overwrite existing dask configuration files and add configuration files for condor
rm -rf $HOME/.config/dask; ln -s /opt/dask $HOME/.config/dask

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

# Populating Dask configuration files
sed -i -e "s|latest|${TAG}|g" $HOME/.config/dask/jobqueue-coffea-casa.yaml
sed -i -e "s|/etc/cmsaf-secrets|${CERT_DIR}|g" $HOME/.config/dask/dask.yaml
sed -i -e "s|CoffeaCasaCluster|${LABEXTENTION_FACTORY_CLASS}|g" $HOME/.config/dask/labextension.yaml
sed -i -e "s|coffea_casa|${LABEXTENTION_FACTORY_MODULE}|g" $HOME/.config/dask/labextension.yaml
sed -i -e "s|UNL HTCondor Cluster|${LABEXTENTION_CLUSTER}|g" $HOME/.config/dask/labextension.yaml

# HTCondor scheduler setting
echo "CONDOR_HOST = ${CONDOR_HOST}" >> $HOME/.condor/config/schedd
echo "COLLECTOR_NAME = ${COLLECTOR_NAME}" >> $HOME/.condor/config/schedd
echo "UID_DOMAIN = ${UID_DOMAIN}" >> $HOME/.condor/config/schedd
echo "SCHEDD_HOST = ${SCHEDD_HOST}" >> $HOME/.condor/config/schedd

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
