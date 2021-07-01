#!/bin/bash

set -x

export PYTHONPATH="$HOME/.local/lib/python3.8/site-packages:$PYTHONPATH"

# ServiceX token generation
if [[ -f "$SERVICEX_TOKEN" ]] && [[ "$SERVICEX_HOST" ]]; then
    export servicex_token=$(<$SERVICEX_TOKEN)
    touch /home/$NB_USER/.servicex
    echo "Tokens: generating ServiceX config file (available only from Jupyterhub notebook)"
    echo "
api_endpoints:
  - endpoint: $SERVICEX_HOST
    type: uproot
    " > $HOME/.servicex

### No need to add tokens until now (when revert please add "token:" in .servicex template)
#    /opt/conda/bin/python -c '
#import yaml, os
#servicex="/home/$NB_USER/.servicex"
#with open(servicex) as f:
#    list_yaml=yaml.load(f,Loader=yaml.Loader)
#list_yaml["api_endpoints"][0]["token"] = os.environ.get("servicex_token")
#with open(servicex, "w") as f:
#    yaml.dump(list_yaml,f)'

#    echo "Tokens: ServiceX config file was succesfully generated."
#    unset servicex_token
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
