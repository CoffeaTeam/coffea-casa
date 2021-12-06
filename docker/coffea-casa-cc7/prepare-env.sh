#!/bin/bash

set -x

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
sed -i -e "s|coffeateam/coffea-casa-analysis|${WORKER_IMAGE}|g" $DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml
sed -i -e "s|latest|${TAG}|g" $DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml
sed -i -e "s|/etc/cmsaf-secrets|${CERT_DIR}|g" $DASK_ROOT_CONFIG/dask.yaml
sed -i -e "s|CoffeaCasaCluster|${LABEXTENTION_FACTORY_CLASS}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|coffea_casa|${LABEXTENTION_FACTORY_MODULE}|g" $DASK_ROOT_CONFIG/labextension.yaml
sed -i -e "s|UNL HTCondor Cluster|${LABEXTENTION_CLUSTER}|g" $DASK_ROOT_CONFIG/labextension.yaml

# FIXME: do we need take in account TLS ans certificates?
if [ "${LABEXTENTION_FACTORY_CLASS:-}" == "KubeCluster" ]; then
  echo "
kubernetes:
  count:
    max: 40
  worker-template:
    metadata:
    spec:
      nodeSelector:
        dask-worker: True
      restartPolicy: Never
      containers:
      - args:
          - dask-worker
          - --nthreads
          - '2'
          - --memory-limit
          - 7GB
          - --death-timeout
          - '60'
          - --nanny
        image: coffeateam/coffea-casa-analysis:${TAG}
        name: dask-worker
        resources:
          limits:
            cpu: "1.75"
            memory: 7G
          requests:
            cpu: 1
            memory: 7G
        volumeMounts:
        - mountPath: ${CERT_DIR}
          name: cmsaf-secrets
  " >> $DASK_ROOT_CONFIG/dask.yaml
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
