#!/bin/bash

set -x

if [[ "$SERVICEX_HOST" ]]; then
    touch $HOME/.servicex
    echo "Tokens: generating ServiceX config file (available only from Jupyterhub notebook)"
    echo "
api_endpoints:
  - name: uproot
    endpoint: $SERVICEX_HOST
    type: uproot
  - name: cms_run1_aod
    endpoint: $SERVICEX_HOST
    type: cms_run1_aod
  - name: open_uproot
    endpoint: $SERVICEX_HOST
    type: open_uproot
    " > $HOME/.servicex
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
