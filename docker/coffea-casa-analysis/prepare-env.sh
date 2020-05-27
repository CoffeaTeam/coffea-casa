#!/bin/bash
set -x

export XCACHE_HOST="red-xcache1.unl.edu"

if [[ -f "/etc/cmsaf-secrets/condor_token" ]]; then
    mkdir -p /home/jovyan/.condor/tokens.d/ && cp /etc/cmsaf-secrets/condor_token /home/jovyan/.condor/tokens.d/condor_token
fi
 
if [ -f "/etc/cmsaf-secrets/xcache_token" ]; then
    export BEARER_TOKEN_FILE="/etc/cmsaf-secrets/xcache_token"
fi

sleep 10

#HTCondor port and hostname
PORT=`cat $_CONDOR_JOB_AD | grep HostPort | tr -d '"' | awk '{print $NF;}'`
HOST=`cat $_CONDOR_JOB_AD | grep RemoteHost | tr -d '"' | tr '@' ' ' | awk '{print $NF;}'`
NAME=`cat $_CONDOR_JOB_AD | grep DaskWorkerName | tr -d '"' | awk '{print $NF;}'`

# for now hardcoded ( --nprocs 1)
HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker 129.93.183.33:8787 --name $NAME --nthreads 4  --memory-limit 2000.00MB --nanny --death-timeout 60"
echo "Copy of the job ClassAd:" 1>&2
cat $_CONDOR_JOB_AD 1>&2
echo $HTCONDOR_COMAND --contact-address tcp://$HOST:$PORT --listen-address tcp://0.0.0.0:8787 1>&2
exec $HTCONDOR_COMAND --contact-address tcp://$HOST:$PORT --listen-address tcp://0.0.0.0:8787