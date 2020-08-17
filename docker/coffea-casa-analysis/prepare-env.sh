#!/bin/bash

set -x

# From JoshKarpel/dask-chtc: wait for the job ad to be updated with <service>_HostPort
# This happens during the first update, usually a few seconds after the job starts
echo "Waiting for HostPort information..."
# Check if we are not in GH CI environment (image check is stuck forever)
if [ ! -z "$GITHUB_WORKFLOW" ]; then
  while true; do
    if grep HostPort "$_CONDOR_JOB_AD"; then
      break
    fi
    sleep 1
  done
  echo "Got HostPort, proceeding..."
  echo
fi

# Condor token
if [[ -f "$PWD/condor_token" ]]; then
    mkdir -p /home/jovyan/.condor/tokens.d/ && cp $PWD/condor_token /home/jovyan/.condor/tokens.d/condor_token
fi

# Bearer token
if [[ -f "$PWD/xcache_token" ]]; then
    export BEARER_TOKEN_FILE="$PWD/xcache_token"
fi

# TLS env ("optional" variables)
if [[ -f "$PWD/ca.pem" ]]; then
    PATH_CA_FILE="$PWD/ca.pem"
fi
# Userkey is concatenated in usercert
if [[ -f "$PWD/hostcert.pem" ]]; then
    FILE_CERT="$PWD/hostcert.pem"
    FILE_KEY="$PWD/hostcert.pem"
fi

if [ ! -z "$PATH_CA_FILE" ] && [ ! -z "$FILE_CERT" ] && [ ! -z "$FILE_KEY" ]; then
    echo 'Info: We have full TLS environment setuped'
    TLS_ENV="true"
else
    echo 'Info: Some CA files are missing, we will launch Dask worker without TLS support'
    TLS_ENV="false"
fi

# HTCondor port, hostname and external IP ("must" variables)
if [ ! -z "$_CONDOR_JOB_AD" ]; then
    PORT=`cat $_CONDOR_JOB_AD | grep HostPort | tr -d '"' | awk '{print $NF;}'`
    HOST=`cat $_CONDOR_JOB_AD | grep RemoteHost | tr -d '"' | tr '@' ' ' | awk '{print $NF;}'`
    NAME=`cat $_CONDOR_JOB_AD | grep "DaskWorkerName "  | tr -d '"' | awk '{print $NF;}'`
    CPUS=`cat $_CONDOR_JOB_AD | grep "DaskWorkerCores " | tr -d '"' | awk '{print $NF;}'`
    MEMORY=`cat $_CONDOR_JOB_AD | grep "RequestMemory " | tr -d '"' | awk '{print $NF;}'`
    MEMORY_MB_FORMATTED=$MEMORY".00MB"
    # Requirement: to add to Condor job decription "+DaskSchedulerAddress": '"tcp://129.93.183.34:8787"',
    EXTERNALIP_PORT=`cat $_CONDOR_JOB_AD | grep DaskSchedulerAddress | tr -d '"' | awk '{print $NF;}'`

    echo "Print ClassAd:" 1>&2
    cat $_CONDOR_JOB_AD 1>&2

    # Dask worker command - for --nprocs is default (=1)
    if [ "$TLS_ENV" == "true" ]; then
        HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker tls://$EXTERNALIP_PORT \
            --name $NAME --tls-ca-file $PATH_CA_FILE --tls-cert $FILE_CERT --tls-key $FILE_KEY \
            --nthreads $CPUS --memory-limit $MEMORY_MB_FORMATTED --nanny --death-timeout 60"
        # --listen-address tls://0.0.0.0:8787   --contact-address tcp://$HOST:$PORT removed because of uncompatibility with --nprocs
        echo $HTCONDOR_COMAND --protocol tls --listen-address tls://0.0.0.0:8787  --contact-address tls://$HOST:$PORT 1>&2
        exec $HTCONDOR_COMAND --protocol tls --listen-address tls://0.0.0.0:8787  --contact-address tls://$HOST:$PORT
    elif  [ "$TLS_ENV" == "false" ]; then
        HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker tcp://$EXTERNALIP_PORT \
            --name $NAME --nthreads $CPUS --memory-limit $MEMORY_MB_FORMATTED --nanny --death-timeout 60"
        echo $HTCONDOR_COMAND --listen-address tcp://0.0.0.0:8787  --contact-address tcp://$HOST:$PORT
        # --listen-address tcp://0.0.0.0:8787  --contact-address tcp://$HOST:$PORT removed because of uncompatibility with --nprocs
        exec $HTCONDOR_COMAND --listen-address tcp://0.0.0.0:8787  --contact-address tcp://$HOST:$PORT
    fi
fi
