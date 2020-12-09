#!/bin/bash

set -x

# servicex token generation
if [[ -f "/etc/cmsaf-secrets/.servicex" ]]; then
    export condor_token=$(</etc/cmsaf-secrets/servicex_token)

    echo "
api_endpoints:
  - endpoint: https://uproot.servicex.coffea.casa
    token:
    type: uproot
    " > $HOME/.servicex

    python -c '
import yaml, os
servicex=os.environ.get("HOME")+"/.servicex"
with open(servicex) as f:
    list_yaml=yaml.load(f,Loader=yaml.Loader)
list_yaml["api_endpoints"][0]["token"] = os.environ.get("condor_token")
with open(servicex, "w") as f:
    yaml.dump(list_yaml,f)'

    unset condor_token
fi

# We start by adding extra apt packages, since pip modules may required library
if [ "$EXTRA_APT_PACKAGES" ]; then
    echo "EXTRA_APT_PACKAGES environment variable found.  Installing."
    apt update -y
    apt install -y $EXTRA_APT_PACKAGES
fi

if [ -e "/opt/app/environment.yml" ]; then
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

# Run extra commands
exec "$@"
