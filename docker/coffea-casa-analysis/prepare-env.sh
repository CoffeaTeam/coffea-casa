#!/bin/bash
set -e

export XCACHE_HOST="red-xcache1.unl.edu"

if [[ -f "/etc/cmsaf-secrets/condor_token" ]]; then
    mkdir -p /home/jovyan/.condor/tokens.d/ && cp /etc/cmsaf-secrets/condor_token /home/jovyan/.condor/tokens.d/condor_token
fi
 
if [ -f "/etc/cmsaf-secrets/xcache_token" ]; then
    export BEARER_TOKEN_FILE="/etc/cmsaf-secrets/xcache_token"
fi

#HTCondor port and hostname
PORT=`cat $_CONDOR_JOB_AD | grep HostPort | tr -d '"' | awk '{print $NF;}'`
HOST=`cat $_CONDOR_JOB_AD | grep RemoteHost | tr -d '"' | tr '@' ' ' | awk '{print $NF;}'`

# for now hardcoded
HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker 129.93.183.33:8787 --nthreads 4 --nprocs 1 --memory-limit 500.00MB --name 0 --nanny --death-timeout 60"
# --contact-address tcp://$HOST:$PORT
exec $HTCONDOR_COMAND --contact-address tcp://$HOST:$PORT --listen-address tcp://0.0.0.0:8787 