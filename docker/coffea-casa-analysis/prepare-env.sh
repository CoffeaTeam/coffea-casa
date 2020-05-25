#!/bin/bash
set -e

export XCACHE_HOST="red-xcache1.unl.edu"

if [[ -f "/etc/cmsaf-secrets/condor_token" ]]; then
    mkdir -p /home/jovyan/.condor/tokens.d/ && cp /etc/cmsaf-secrets/condor_token /home/jovyan/.condor/tokens.d/condor_token
fi
 
if [ -f "/etc/cmsaf-secrets/xcache_token" ]; then
    export BEARER_TOKEN_FILE="/etc/cmsaf-secrets/xcache_token"
fi