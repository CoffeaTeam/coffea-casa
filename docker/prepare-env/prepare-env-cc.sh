#!/bin/bash

set -x

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

# HTCondor scheduler settings
echo "CONDOR_HOST = ${CONDOR_HOST}" >> /opt/condor/config.d/schedd
echo "COLLECTOR_NAME = ${COLLECTOR_NAME}" >> /opt/condor/config.d/schedd
echo "UID_DOMAIN = ${UID_DOMAIN}" >> /opt/condor/config.d/schedd
echo "SCHEDD_HOST = ${SCHEDD_HOST}" >> /opt/condor/config.d/schedd

# Configure oidc-agent for token management
#echo "eval \`oidc-keychain\`" >> ~/.bashrc
#eval `oidc-keychain`
#oidc-gen coffea-casa --issuer $IAM_SERVER \
#               --client-id $IAM_CLIENT_ID \ # https://cms-auth.web.cern.ch/
#               --client-secret $IAM_CLIENT_SECRET \
#               --rt $REFRESH_TOKEN \
#               --confirm-yes \
#               --scope "openid profile email wlcg wlcg.groups" \
#               --redirect-uri  http://localhost:8843 \
#               --pw-cmd "echo \"DUMMY PWD\""

#while true; do oidc-token coffea-casa --time 1200 > /tmp/token; sleep 600; done &

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
exec "/usr/local/bin/prepare-env.sh" "$@"
