#!/usr/bin/env bash
set -Eeuo pipefail

[[ "${DEBUG:-}" == "1" ]] && set -x

CONDA_BIN="/usr/local/bin"
JOB_AD="${_CONDOR_JOB_AD:-}"
JOB_IWD="${_CONDOR_JOB_IWD:-}"

########################################
# Conda init
########################################

if [[ -f "$CONDA_BIN/conda" ]]; then
    eval "$("$CONDA_BIN/conda" shell.bash hook)"
else
    echo "Conda not found at $CONDA_BIN/conda"
fi

########################################
# Conda / Pip extra packages
########################################

if [[ -n "${EXTRA_CONDA_PACKAGES:-}" ]]; then
    echo "Installing EXTRA_CONDA_PACKAGES..."
    "$CONDA_BIN/mamba" install -y ${EXTRA_CONDA_PACKAGES}
fi

if [[ -n "${EXTRA_PIP_PACKAGES:-}" ]]; then
    echo "Installing EXTRA_PIP_PACKAGES..."
    "$CONDA_BIN/pip" install ${EXTRA_PIP_PACKAGES}
fi

########################################
# Exit early if running as sidecar
########################################

if [[ -v COFFEA_CASA_SIDECAR ]]; then
    exec "$@"
fi

########################################
# Wait for required ClassAd fields
########################################

wait_for_key() {
    local key="$1"
    echo "Waiting for $key..."
    until grep -q "$key" "$JOB_AD"; do
        sleep 1
    done
    echo "$key detected."
}

if [[ "${GITHUB_ACTIONS:-}" != "true" ]]; then
    wait_for_key "dask_HostPort"
    wait_for_key "nanny_HostPort"
fi

[[ -z "$JOB_IWD" ]] && { echo "Missing _CONDOR_JOB_IWD"; exit 1; }

########################################
# Secure file transfers
########################################

copy_if_exists() {
    local src="$1"
    local dst="$2"
    [[ -f "$src" ]] && mkdir -p "$(dirname "$dst")" && cp "$src" "$dst"
}

copy_if_exists "$JOB_IWD/condor_token" \
               "${SEC_TOKEN_SYSTEM_DIRECTORY:-}/condor_token"
copy_if_exists "$JOB_IWD/access_token" "/tmp/.xcache/access_token"

########################################
# Environment installation
########################################

if [[ -f "$JOB_IWD/environment.yml" || -f "$JOB_IWD/environment.yaml" ]]; then
    ENV_FILE=$(ls "$JOB_IWD"/environment.y*ml | head -1)
    echo "Updating conda environment..."
    "$CONDA_BIN/mamba" env update -n base -f "$ENV_FILE"
fi

if [[ -f "$JOB_IWD/requirements.txt" ]]; then
    echo "Installing pip requirements..."
    "$CONDA_BIN/python" -m pip install -r "$JOB_IWD/requirements.txt"
fi

########################################
# Parse ClassAd safely (single awk pass)
########################################

if [[ -n "$JOB_AD" ]]; then
    declare -A AD

    while IFS='=' read -r key value; do
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | tr -d '"' | xargs)
        AD["$key"]="$value"
    done < "$JOB_AD"

    HOST=$(echo "${AD[StartdIpAddr]:-}" | sed 's/<\([^:]*\).*/\1/')
    WORKER_TYPE="${AD[CoffeaCasaWorkerType]:-dask}"

    echo "Loaded ClassAd:"
    cat "$JOB_AD" >&2

    if [[ "$WORKER_TYPE" == "dask" ]]; then
        MEMORY_MB="${AD[MemoryProvisioned]}.00MB"

        exec python -m distributed.cli.dask_worker "${AD[DaskSchedulerAddress]}" \
            --name "${AD[DaskWorkerName]}" \
            --tls-ca-file "${JOB_IWD}/ca.pem" \
            --tls-cert "${JOB_IWD}/hostcert.pem" \
            --tls-key "${JOB_IWD}/hostcert.pem" \
            --nthreads "${AD[DaskWorkerCores]}" \
            --memory-limit "$MEMORY_MB" \
            --nanny \
            --death-timeout 60 \
            --protocol tls \
            --lifetime 7200 \
            --listen-address "tls://0.0.0.0:${AD[dask_ContainerPort]}" \
            --contact-address "tls://${HOST}:${AD[dask_HostPort]}"

    elif [[ "$WORKER_TYPE" == "taskvine" ]]; then
        DISK_MB=$(( AD[DiskProvisioned] / 1024 ))

        exec vine_worker --ssl -dall \
            --contact-hostport "$HOST:${AD[dask_HostPort]}" \
            --transfer-port "${AD[dask_ContainerPort]}" \
            --cores "${AD[CpusProvisioned]}" \
            --memory "${AD[MemoryProvisioned]}" \
            --disk "$DISK_MB" \
            --timeout 7200 \
            "${AD[DaskSchedulerAddress]%:*}" \
            "${AD[DaskSchedulerAddress]##*:}"
    fi
fi

########################################
# Default fallback
########################################

exec "$@"
