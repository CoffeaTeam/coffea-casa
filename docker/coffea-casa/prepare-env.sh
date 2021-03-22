#!/bin/bash

set -x

export PYTHONPATH="$HOME/.local/lib/python3.8/site-packages:$PYTHONPATH"

# servicex token generation
if [[ -f "/etc/cmsaf-secrets/.servicex" ]]; then
    export servicex_token=$(</etc/cmsaf-secrets/.servicex)
    # debug: it work locally in Hub, let's try to touch file
    touch /home/jovyan/.servicex
    echo "Tokens: generating ServiceX config file."
    # We are using dev instance to test JWT integration:
    # replace later with https://uproot.servicex.coffea.casa
    echo "
api_endpoints:
  - endpoint: https://uproot-dev.servicex.coffea.casa
    token:
    type: uproot
    " > /home/jovyan/.servicex

    /opt/conda/bin/python -c '
import yaml, os
servicex="/home/jovyan/.servicex"
with open(servicex) as f:
    list_yaml=yaml.load(f,Loader=yaml.Loader)
list_yaml["api_endpoints"][0]["token"] = os.environ.get("servicex_token")
with open(servicex, "w") as f:
    yaml.dump(list_yaml,f)'

    echo "Tokens: ServiceX config file was succesfully generated."
    unset servicex_token
fi

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
