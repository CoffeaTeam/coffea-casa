#!/bin/bash

set -x

# Testing ---------->
echo " DEBUG: Our directory is: $PWD"

# xcache setup
export XCACHE_HOST="red-xcache1.unl.edu"

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
if [[ -f "$PWD/usercert.pem" ]]; then
    FILE_CERT="$PWD/usercert.pem"
    FILE_KEY="$PWD/usercert.pem"
fi

if [ -n "$PATH_CA_FILE" ] && [ -n "$FILE_CERT" ] && [ -n "$FILE_KEY" ]; then
    echo 'Info: We have full TLS environment setuped'        
    TLS_ENV=true
else
    echo 'Info: Some CA files are missing, we will launch Dask worker without TLS support'
    TLS_ENV=false
fi

# Small hack for Dask scheduler (to be investigated)
sleep 10

# HTCondor port, hostname and external IP ("must" variables)
PORT=`cat $_CONDOR_JOB_AD | grep HostPort | tr -d '"' | awk '{print $NF;}'`
HOST=`cat $_CONDOR_JOB_AD | grep RemoteHost | tr -d '"' | tr '@' ' ' | awk '{print $NF;}'`
NAME=`cat $_CONDOR_JOB_AD | grep DaskWorkerName | tr -d '"' | awk '{print $NF;}'`
# Requirement: to add to Condor job decription "+DaskSchedulerAddress": '"tcp://129.93.183.34:8787"',
EXTERNALIP_PORT=`cat $_CONDOR_JOB_AD | grep DaskSchedulerAddress | tr -d '"' | awk '{print $NF;}'`

# Dask worker command - for --nprocs is default (=1)
if [ "$TLS_ENV" = true ]; then
    HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker $EXTERNALIP_PORT \
        --name $NAME --tls-ca-file $PATH_CA_FILE --tls-cert $FILE_CERT --tls-key $FILE_KEY \
        --nthreads 4  --memory-limit 2000.00MB --nanny --death-timeout 60"
else
    HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker $EXTERNALIP_PORT \
        --name $NAME --nthreads 4  --memory-limit 2000.00MB --nanny --death-timeout 60"
fi

echo "Copy of the job ClassAd:" 1>&2
cat $_CONDOR_JOB_AD 1>&2
echo $HTCONDOR_COMAND --contact-address tcp://$HOST:$PORT --listen-address tcp://0.0.0.0:8787 1>&2
exec $HTCONDOR_COMAND --contact-address tcp://$HOST:$PORT --listen-address tcp://0.0.0.0:8787
