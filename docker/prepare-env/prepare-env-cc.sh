#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${DEBUG:-}" == "1" ]] && set -x

CONDA_BIN="/usr/local/bin"
SCHEdd_CONF="/opt/condor/config.d/schedd"

########################################
# Conda init
########################################

if [[ -f "$CONDA_BIN/conda" ]]; then
    eval "$("$CONDA_BIN/conda" shell.bash hook)"
else
    echo "Conda not found at $CONDA_BIN/conda"
fi

########################################
# Enable git completion (if available)
########################################

[[ -f /usr/share/bash-completion/completions/git ]] && \
    source /usr/share/bash-completion/completions/git

########################################
# ServiceX config
########################################

if [[ -n "${SERVICEX_HOST:-}" && -n "${SERVICEX_TYPE:-}" ]]; then
    cat > "$HOME/.servicex" <<EOF
api_endpoints:
  - name: ${SERVICEX_TYPE}
    endpoint: ${SERVICEX_HOST}
    type: ${SERVICEX_TYPE}
EOF
    echo "ServiceX config generated."
fi

########################################
# Dask configuration templating
########################################

replace() {
    local file="$1"
    local search="$2"
    local replace="$3"
    [[ -f "$file" ]] && \
        sed -i "s|${search}|${replace}|g" "$file"
}

replace "$DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml" \
        "hub.opensciencegrid.org/coffea-casa/cc-analysis-ubuntu" \
        "${WORKER_IMAGE:-}"

replace "$DASK_ROOT_CONFIG/jobqueue-coffea-casa.yaml" \
        "development" \
        "${TAG:-}"

replace "$DASK_ROOT_CONFIG/dask_tls.yaml" \
        "/etc/cmsaf-secrets" \
        "${CERT_DIR:-}"

replace "$DASK_ROOT_CONFIG/labextension.yaml" \
        "LocalCluster" \
        "${LABEXTENTION_FACTORY_CLASS:-}"

replace "$DASK_ROOT_CONFIG/labextension.yaml" \
        "dask.distributed" \
        "${LABEXTENTION_FACTORY_MODULE:-}"

replace "$DASK_ROOT_CONFIG/labextension.yaml" \
        "Local Cluster" \
        "${LABEXTENTION_CLUSTER:-}"

if [[ "${LABEXTENTION_FACTORY_CLASS:-}" == "LocalCluster" ]]; then
    replace "$DASK_ROOT_CONFIG/dask_tls.yaml" \
            "require-encryption: True" \
            "require-encryption: False"
fi

########################################
# HTCondor scheduler config
########################################

{
    echo "CONDOR_HOST = ${CONDOR_HOST:-}"
    echo "COLLECTOR_NAME = ${COLLECTOR_NAME:-}"
    echo "UID_DOMAIN = ${UID_DOMAIN:-}"
    echo "SCHEDD_HOST = ${SCHEDD_HOST:-}"
    echo "DELEGATE_JOB_GSI_CREDENTIALS = FALSE"
} >> "$SCHEdd_CONF"


########################################
# Environment installation
########################################

# Check for environment.yaml or environment.yml and update the environment
# Determine which environment file to use
ENV_FILE=""
if [ -s "$HOME/environment.yaml" ]; then
    ENV_FILE="$HOME/environment.yaml"
elif [ -s "$HOME/environment.yml" ]; then
    ENV_FILE="$HOME/environment.yml"
fi

# Update conda environment if a valid YAML was found
if [ -n "$ENV_FILE" ]; then
    echo "Updating conda environment from $(basename "$ENV_FILE")"
    "$CONDA_BIN/mamba" env update -f "$ENV_FILE"
fi

# Install Python packages from requirements.txt if it exists
if [ -f "$HOME/requirements.txt" ]; then
    "$CONDA_BIN/python" -m pip install -r "$HOME/requirements.txt"
fi

########################################
# Extra packages
########################################

[[ -n "${EXTRA_CONDA_PACKAGES:-}" ]] && \
    "$CONDA_BIN/mamba" install -y ${EXTRA_CONDA_PACKAGES}

[[ -n "${EXTRA_PIP_PACKAGES:-}" ]] && \
    "$CONDA_BIN/pip" install ${EXTRA_PIP_PACKAGES}

########################################
# Execute main process
########################################

exec "$@"
