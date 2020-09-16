#!/bin/bash

set -x

# We start by adding extra apt packages, since pip modules may required library
if [ "$EXTRA_APT_PACKAGES" ]; then
    echo "EXTRA_APT_PACKAGES environment variable found.  Installing."
    apt update -y
    apt install -y $EXTRA_APT_PACKAGES
fi

if [ -e "$PWD/environment.yml" ]; then
    echo "environment.yml found. Installing packages"
    /opt/conda/bin/conda env update -f /opt/app/environment.yml
else
    echo "no environment.yml"
fi

if [ "$EXTRA_CONDA_PACKAGES" ]; then
    echo "EXTRA_CONDA_PACKAGES environment variable found.  Installing."
    /opt/conda/bin/conda install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "EXTRA_PIP_PACKAGES environment variable found.  Installing".
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# If there is defined COFFEA_CASA_SIDECAR env variable (inside hub values.yml),
# then we use this container as a sidecar for JHUB with command:
# dask-worker tls://localhost:8786 --tls-ca-file /etc/cmsaf-secrets/ca.pem \
# --tls-cert /etc/cmsaf-secrets/hostcert.pem --tls-key /etc/cmsaf-secrets/hostcert.pem \
# --listen-address tls://0.0.0.0:8788 --name kubernetes-worker --contact-address \
# tls://$HOST_IP:8786
if [[ -v COFFEA_CASA_SIDECAR ]]; then
  # From chtc/dask-chtc: wait for the job ad to be updated with <service>_HostPort
  # This happens during the first update, usually a few seconds after the job starts
  echo "Waiting for HostPort information..."
  # Check if we are not in GH CI environment (otherwise image check will stuck forever)
  # docs: Always set to true when GitHub Actions is running the workflow.
  # You can use this variable to differentiate when tests are being run locally or by GitHub Actions.
  if [[ -z "$GITHUB_ACTIONS" ]]; then
    while true; do
      if grep HostPort "$_CONDOR_JOB_AD"; then
        break
      fi
      sleep 1
    done
    echo "Got HostPort, proceeding..."
    echo
  fi

  # Condor token securily transfered from scheduler
  if [[ -f "$PWD/condor_token" ]]; then
      mkdir -p /home/jovyan/.condor/tokens.d/ && cp $PWD/condor_token /home/jovyan/.condor/tokens.d/condor_token
  fi
  # Bearer token
  if [[ -f "$PWD/xcache_token" ]]; then
      export BEARER_TOKEN_FILE="$PWD/xcache_token"
  fi
  # CA certificate securily transfered from scheduler
  if [[ -f "$PWD/ca.pem" ]]; then
      PATH_CA_FILE="$PWD/ca.pem"
  fi
  # Hostcertn securily transfered from scheduler and
  # userkey here is simply concatenated in usercert
  if [[ -f "$PWD/hostcert.pem" ]]; then
      FILE_CERT="$PWD/hostcert.pem"
      FILE_KEY="$PWD/hostcert.pem"
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
      --nanny --death-timeout 60" \
      --protocol tls \
      --listen-address tls://0.0.0.0:$CONTAINER_PORT \
      --contact-address tls://$HOST:$PORT
      # Debug print
      echo $HTCONDOR_COMAND 1>&2
      exec $HTCONDOR_COMAND --protocol tls --listen-address tls://0.0.0.0:$CONTAINER_PORT  --contact-address tls://$HOST:$PORT
  fi
fi
