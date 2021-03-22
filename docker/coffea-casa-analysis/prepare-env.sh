#!/bin/bash

set -x

export PYTHONPATH="$HOME/.local/lib/python3.8/site-packages:$PYTHONPATH"

# Debug 'random' name for kubernetes worker
WORKER_ID=$(cat /dev/urandom | tr -dc '0-9' | fold -w 256 | head -n 1 | sed -e 's/^0*//' | head --bytes 5)
sed --in-place "s/kubernetes-worker-%(ENV_WORKER_ID)s/kubernetes-worker-${WORKER_ID}/g" /etc/supervisor/supervisord.conf

if [ "$EXTRA_CONDA_PACKAGES" ]; then
    echo "conda: EXTRA_CONDA_PACKAGES environment variable found.  Installing."
    /opt/conda/bin/conda install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "pip: EXTRA_PIP_PACKAGES environment variable found.  Installing"
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# If there is defined COFFEA_CASA_SIDECAR env variable (inside hub values.yml),
# then we use this container as a sidecar for JHUB with command:
# dask-worker tls://localhost:8786 --tls-ca-file /etc/cmsaf-secrets/ca.pem \
# --tls-cert /etc/cmsaf-secrets/hostcert.pem --tls-key /etc/cmsaf-secrets/hostcert.pem \
# --listen-address tls://0.0.0.0:8788 --name kubernetes-worker --contact-address \
# tls://$HOST_IP:8786
if [[ ! -v COFFEA_CASA_SIDECAR ]]; then
  # From chtc/dask-chtc: wait for the job ad to be updated with <service>_HostPort
  # This happens during the first update, usually a few seconds after the job starts
  echo "Waiting for HostPort information..."
  # Check if we are not in GH CI environment (otherwise image check will stuck forever)
  # docs: Always set to true when GitHub Actions is running the workflow.
  # You can use this variable to differentiate when tests are being run locally or by GitHub Actions.
  if [ ! -z "$GITHUB_ACTIONS" ] || [ "$GITHUB_ACTIONS" != 'true' ]; then
    while true; do
      if grep HostPort "$_CONDOR_JOB_AD"; then
        break
      fi
      sleep 1
    done
    echo "Got HostPort, proceeding..."
    echo
  fi

  if [ -z "$_CONDOR_JOB_IWD" ]; then
    echo "Error: something is wrong, $_CONDOR_JOB_IWD (path to the initial working directory the job was born with) was not defined!"
    exit 1
  fi

  # Condor token securily transfered from scheduler
  if [[ -f "$_CONDOR_JOB_IWD/condor_token" ]]; then
      mkdir -p /home/jovyan/.condor/tokens.d/ && cp $_CONDOR_JOB_IWD/condor_token /home/jovyan/.condor/tokens.d/condor_token
  fi
  # Bearer token
  if [[ -f "$_CONDOR_JOB_IWD/xcache_token" ]]; then
      export BEARER_TOKEN_FILE="$_CONDOR_JOB_IWD/xcache_token"
      export XCACHE_HOST="red-xcache1.unl.edu"
      export XRD_PLUGINCONFDIR="/opt/conda/etc/xrootd/client.plugins.d/"
      export LD_LIBRARY_PATH="/opt/conda/lib/:$LD_LIBRARY_PATH"
      export XRD_PLUGIN="/opt/conda/lib/libXrdClAuthzPlugin.so"
  fi
  
  if [ -e "$_CONDOR_JOB_IWD/environment.yml" ]; then
    echo "Conda: environment.yml found. Installing packages."
    /opt/conda/bin/conda env update -f $_CONDOR_JOB_IWD/environment.yml
  elif [ -e "$_CONDOR_JOB_IWD/environment.yaml" ]; then
    echo "Conda: environment.yaml found. Installing packages."
    /opt/conda/bin/conda env update -f $_CONDOR_JOB_IWD/environment.yaml
  else
    echo "No environment.yml, conda will not install any package."
  fi

  if [ -e "$_CONDOR_JOB_IWD/requirements.txt" ]; then
    echo "Pip: requirements.txt found. Installing packages."
    /opt/conda/bin/python -m pip install -r $_CONDOR_JOB_IWD/requirements.txt
  else
    echo "No requirements.txt, pip will not install any module."
  fi
  
  # CA certificate securily transfered from scheduler
  if [[ -f "$_CONDOR_JOB_IWD/ca.pem" ]]; then
      PATH_CA_FILE="$_CONDOR_JOB_IWD/ca.pem"
  fi
  # Hostcertn securily transfered from scheduler and
  # userkey here is simply concatenated in usercert
  if [[ -f "$_CONDOR_JOB_IWD/hostcert.pem" ]]; then
      FILE_CERT="$_CONDOR_JOB_IWD/hostcert.pem"
      FILE_KEY="$_CONDOR_JOB_IWD/hostcert.pem"
  fi

  # HTCondor port, hostname and external IP ("must" variables)
  if [ ! -z "$_CONDOR_JOB_AD" ]; then
      # We make sure that we use proper configuration (dask worker name, ports, number of CPUs,
      # memory requested for worker, hostname of scheduler), parcing HTCondor Job AD file
      PORT=`cat $_CONDOR_JOB_AD | grep HostPort | tr -d '"' | awk '{print $NF;}'`
      CONTAINER_PORT=`cat $_CONDOR_JOB_AD | grep ContainerPort | tr -d '"' | awk '{print $NF;}'`
      HOST=`cat $_CONDOR_JOB_AD | grep RemoteHost | tr -d '"' | tr '@' ' ' | awk '{print $NF;}'`
      NAME=`cat $_CONDOR_JOB_AD | grep "DaskWorkerName "  | tr -d '"' | awk '{print $NF;}'`
      CPUS=`cat $_CONDOR_JOB_AD | grep "DaskWorkerCores " | tr -d '"' | awk '{print $NF;}'`
      MEMORY=`cat $_CONDOR_JOB_AD | grep "RequestMemory " | tr -d '"' | awk '{print $NF;}'`
      MEMORY_MB_FORMATTED=$MEMORY".00MB"
      # Requirement: to add to Condor job decription "+DaskSchedulerAddress": '"tcp://129.93.183.34:8787"',
      EXTERNALIP_PORT=`cat $_CONDOR_JOB_AD | grep DaskSchedulerAddress | tr -d '"' | awk '{print $NF;}'`

      echo "Print ClassAd:" 1>&2
      cat $_CONDOR_JOB_AD 1>&2

      # Dask worker command execurted in HTCondor pool.
      # Communication protocol: in Coffea-casa we use only secured communications (over TLS)
      HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker $EXTERNALIP_PORT \
      --name $NAME \
      --tls-ca-file $PATH_CA_FILE \
      --tls-cert $FILE_CERT \
      --tls-key $FILE_KEY \
      --nthreads $CPUS \
      --memory-limit $MEMORY_MB_FORMATTED \
      --nanny --death-timeout 60 \
      --protocol tls \
      --listen-address tls://0.0.0.0:$CONTAINER_PORT \
      --contact-address tls://$HOST:$PORT"
      # Debug print
      echo $HTCONDOR_COMAND 1>&2
      exec $HTCONDOR_COMAND
  fi
else
  exec "$@"
fi
