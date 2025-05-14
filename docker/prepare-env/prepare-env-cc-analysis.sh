#!/bin/bash

set -x

if [ "$EXTRA_CONDA_PACKAGES" ]; then
    echo "conda: EXTRA_CONDA_PACKAGES environment variable found.  Installing."
    /opt/conda/bin/mamba install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "pip: EXTRA_PIP_PACKAGES environment variable found.  Installing"
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# If there is defined COFFEA_CASA_SIDECAR env variable (inside hub values.yml),
# then we use this container as a sidecar for notebook.
if [[ ! -v COFFEA_CASA_SIDECAR ]]; then
  if [ "${GITHUB_ACTIONS:-}" == "true" ]; then
    echo "CI mode, no need to test dask_HostPort info..."
  else
    # From chtc/dask-chtc: wait for the job ad to be updated with <service>_HostPort
    # This happens during the first update, usually a few seconds after the job starts
    echo "Waiting for dask_HostPort and nanny_HostPort information..."
    # Check if we are not in GH CI environment (otherwise image check will stuck forever)
    # docs: Always set to true when GitHub Actions is running the workflow.
    # You can use this variable to differentiate when tests are being run locally or by GitHub Actions.
    while true; do
      if grep dask_HostPort "$_CONDOR_JOB_AD"; then
        break
      fi
      sleep 1
    done
    echo "Got dask_HostPort, proceeding..."
    echo

    while true; do
      if grep nanny_HostPort "$_CONDOR_JOB_AD"; then
        break
      fi
      sleep 1
    done
    echo "Got nanny_HostPort, proceeding..."
    echo

    if [ -z "$_CONDOR_JOB_IWD" ]; then
      echo "Error: something is wrong, $_CONDOR_JOB_IWD (path to the initial working directory the job was born with) was not defined!"
      exit 1
    fi
  fi

  # Condor token securily transfered from scheduler
  if [[ -f "$_CONDOR_JOB_IWD/condor_token" ]]; then
      mkdir -p $SEC_TOKEN_SYSTEM_DIRECTORY && cp $_CONDOR_JOB_IWD/condor_token $SEC_TOKEN_SYSTEM_DIRECTORY/condor_token
  fi

  if [[ -f "$_CONDOR_JOB_IWD/ceph.conf" ]]; then
      cp $_CONDOR_JOB_IWD/ceph.conf ${CEPH_DIR}
  fi

    if [[ -f "$_CONDOR_JOB_IWD/access_token" ]]; then
      mkdir -p /tmp/.xcache && cp $_CONDOR_JOB_IWD/access_token  /tmp/.xcache/access_token
  fi

  if [[ -f "$_CONDOR_JOB_IWD/keyring" ]]; then
      cp $_CONDOR_JOB_IWD/keyring ${CEPH_DIR}
  fi
  
  if [ -e "$_CONDOR_JOB_IWD/environment.yml" ]; then
    echo "Conda: environment.yml found. Installing packages."
    /opt/conda/bin/mamba env update -n base -f $_CONDOR_JOB_IWD/environment.yml
  elif [ -e "$_CONDOR_JOB_IWD/environment.yaml" ]; then
    echo "Conda: environment.yaml found. Installing packages."
    /opt/conda/bin/mamba env update -n base -f $_CONDOR_JOB_IWD/environment.yaml
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
      # memory requested for worker, hostname of scheduler), parcing HTCondor Job AD file`
      # Nanny container port will be used later...
      PORT=`cat $_CONDOR_JOB_AD | grep dask_HostPort | tr -d '"' | awk '{print $NF;}'`
      NANNYPORT=`cat $_CONDOR_JOB_AD | grep nanny_HostPort | tr -d '"' | awk '{print $NF;}'`
      NANNYCONTAINER_PORT=`cat $_CONDOR_JOB_AD | grep nanny_ContainerPort | tr -d '"' | awk '{print $NF;}'`
      CONTAINER_PORT=`cat $_CONDOR_JOB_AD | grep dask_ContainerPort | tr -d '"' | awk '{print $NF;}'`
      #FIXME:
      #NANNY_PORT=`cat $_CONDOR_JOB_AD | grep nanny_HostPort | tr -d '"' | awk '{print $NF;}'`
      #NANNYCONTAINER_PORT=`cat $_CONDOR_JOB_AD | grep nanny_ContainerPort | tr -d '"' | awk '{print $NF;}'`
      #HOST=`cat $_CONDOR_JOB_AD | grep RemoteHost | tr -d '"' | tr '@' ' ' | awk '{print $NF;}'`
      HOST=`cat $_CONDOR_JOB_AD | grep StartdIpAddr | sed 's/StartdIpAddr = \"<\([^:]*\).*/\1/'`
      NAME=`cat $_CONDOR_JOB_AD | grep "DaskWorkerName "  | tr -d '"' | awk '{print $NF;}'`
      # Requirement: to add to Condor job decription "+DaskSchedulerAddress": '"tcp://129.93.183.34:8787"',
      EXTERNALIP_PORT=`cat $_CONDOR_JOB_AD | grep DaskSchedulerAddress | tr -d '"' | awk '{print $NF;}'`
      # From jthiltges 
      #WORKER_LIFETIME=${WORKER_LIFETIME:-1 hour}

      WORKER_TYPE=`cat $_CONDOR_JOB_AD | grep "CoffeaCasaWorkerType " | tr -d '"' | awk '{print $NF;}'`

      CPUS_PROVISIONED=`cat $_CONDOR_JOB_AD | grep "CpusProvisioned " | tr -d '"' | awk '{print $NF;}'`
      MEMORY_PROVISIONED=`cat $_CONDOR_JOB_AD | grep "MemoryProvisioned " | tr -d '"' | awk '{print $NF;}'`
      DISK_PROVISIONED=`cat $_CONDOR_JOB_AD | grep "DiskProvisioned " | tr -d '"' | awk '{print $NF;}'`

      echo "Print ClassAd:" 1>&2
      cat $_CONDOR_JOB_AD 1>&2

      if [ -z "${WORKER_TYPE}" ] || [ "${WORKER_TYPE}" = dask ]
      then
	      CPUS=`cat $_CONDOR_JOB_AD | grep "DaskWorkerCores " | tr -d '"' | awk '{print $NF;}'`
	      MEMORY=`cat $_CONDOR_JOB_AD | grep "RequestMemory " | tr -d '"' | awk '{print $NF;}'`
	      MEMORY_MB_FORMATTED=$MEMORY_PROVISIONED".00MB"

	      # Dask worker command execurted in HTCondor pool.
	      # Communication protocol: in Coffea-casa we use only secured communications (over TLS)
	      # re-apply John's patch and add:    --nanny-contact-address tls://$HOST:$NANNYPORT --nanny-port $NANNYCONTAINER_PORT \ \
	      HTCONDOR_COMMAND="python -m distributed.cli.dask_worker $EXTERNALIP_PORT \
	      --name $NAME \
	      --tls-ca-file $PATH_CA_FILE \
	      --tls-cert $FILE_CERT \
	      --tls-key $FILE_KEY \
	      --nthreads $CPUS \
	      --memory-limit $MEMORY_MB_FORMATTED \
	      --nanny \
	      --death-timeout 60 \
	      --protocol tls \
	      --lifetime 7200 \
	      --listen-address tls://0.0.0.0:$CONTAINER_PORT \
	      --contact-address tls://$HOST:$PORT"
      elif [ "${WORKER_TYPE}" = taskvine ]
      then
	      DISK_MB=$((DISK_PROVISIONED/1024))
	      MANAGER_HOST=${EXTERNALIP_PORT%:*}
	      MANAGER_HOST=${MANAGER_HOST#*tls:\/\/}        # XXX: fix on vine_worker, it should parsing this
	      MANAGER_PORT=${EXTERNALIP_PORT##*:}

	      HTCONDOR_COMMAND="vine_worker --ssl -dall \
	      --contact-hostport $HOST:$PORT \
	      --transfer-port $CONTAINER_PORT \
	      --cores $CPUS_PROVISIONED \
	      --memory $MEMORY_PROVISIONED \
	      --disk $DISK_MB \
	      --timeout 7200 \
	      $MANAGER_HOST $MANAGER_PORT"
      else
	      HTCONDOR_COMMAND="$@"
      fi

      # Debug print
      echo $HTCONDOR_COMMAND 1>&2
      exec $HTCONDOR_COMMAND

      export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/opt/combine/CombinedLimit/build/lib"
  fi
else
  exec "$@"
fi
