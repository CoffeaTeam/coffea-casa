#!/bin/bash
set -x

# Pure ClassAd-parsing / command-building helpers, kept in a sourceable library
# so they can be unit-tested without running this entrypoint.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=worker-args.sh
source "$SCRIPT_DIR/worker-args.sh" || {
    echo "Error: cannot source worker-args.sh from $SCRIPT_DIR" 1>&2
    exit 1
}

########################################
# Conda init
########################################
if [[ -f "$CONDA_BIN/conda" ]]; then
    eval "$("$CONDA_BIN/conda" shell.bash hook)"
else
    echo "Conda not found at $CONDA_BIN/conda"
fi

if [ "$EXTRA_CONDA_PACKAGES" ]; then
    echo "conda: EXTRA_CONDA_PACKAGES environment variable found. Installing."
    /opt/conda/bin/mamba install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "pip: EXTRA_PIP_PACKAGES environment variable found. Installing"
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# If COFFEA_CASA_SIDECAR is defined (inside hub values.yml), this container is a
# sidecar for the notebook and skips the worker bring-up.
if [[ ! -v COFFEA_CASA_SIDECAR ]]; then
    if [ "${GITHUB_ACTIONS:-}" == "true" ]; then
        echo "CI mode, no need to test dask_HostPort info..."
    else
        # Wait (up to 30s) for a *defined* dask_HostPort / nanny_HostPort.
        # Newer HTCondor writes these as "undefined" on the first ad update and
        # fills in the real forwarded port a moment later. Grepping only the
        # attribute *name* (the old behavior) matched "= undefined" and raced
        # ahead, so the worker was launched with tls://host:undefined and died
        # in ~3s. Here we wait for an actual value; ad_get comes from
        # worker-args.sh, which is sourced above. If the port never becomes
        # defined (e.g. host-networked node), we proceed anyway and
        # cc_build_worker_command falls back to the container port.
        echo "Waiting for a defined dask_HostPort / nanny_HostPort (up to 30s)..."
        for _i in $(seq 1 30); do
            _dh=$(ad_get "$_CONDOR_JOB_AD" dask_HostPort)
            _nh=$(ad_get "$_CONDOR_JOB_AD" nanny_HostPort)
            if [ -n "$_dh" ] && [ "$_dh" != "undefined" ] \
               && [ -n "$_nh" ] && [ "$_nh" != "undefined" ]; then
                echo "Got dask_HostPort=$_dh nanny_HostPort=$_nh, proceeding..."
                break
            fi
            sleep 1
        done
        if [ -z "$_dh" ] || [ "$_dh" = "undefined" ] \
           || [ -z "$_nh" ] || [ "$_nh" = "undefined" ]; then
            echo "WARNING: dask_HostPort/nanny_HostPort still undefined after 30s;" \
                 "falling back to the container port (host-networked node?)." 1>&2
        fi
        echo
        if [ -z "$_CONDOR_JOB_IWD" ]; then
            echo "Error: \$_CONDOR_JOB_IWD (initial working directory) was not defined!"
            exit 1
        fi
    fi

    # Condor token securely transferred from scheduler
    if [[ -f "$_CONDOR_JOB_IWD/condor_token" ]]; then
        mkdir -p $SEC_TOKEN_SYSTEM_DIRECTORY && cp $_CONDOR_JOB_IWD/condor_token $SEC_TOKEN_SYSTEM_DIRECTORY/condor_token
    fi

    if [[ -f "$_CONDOR_JOB_IWD/ceph.conf" ]]; then
        cp $_CONDOR_JOB_IWD/ceph.conf ${CEPH_DIR}
    fi

    if [[ -f "$_CONDOR_JOB_IWD/access_token" ]]; then
        mkdir -p /tmp/.xcache && cp $_CONDOR_JOB_IWD/access_token /tmp/.xcache/access_token
    fi

    if [[ -f "$_CONDOR_JOB_IWD/keyring" ]]; then
        cp $_CONDOR_JOB_IWD/keyring ${CEPH_DIR}
    fi

    if [ -e "$_CONDOR_JOB_IWD/environment.yml" ]; then
        echo "Conda: environment.yml found. Installing packages."
        /opt/conda/bin/mamba env update -n base -f $_CONDOR_JOB_IWD/environment.yml
    elif [ -e "$_CONDOR_JOB_IWD/environment.yaml" ]; then
        echo "Conda: environment.yaml found. Installing packages."
        /opt/conda/bin/mamba env update -n base -f $_CONDOR_JOB_IWD/environment.yaml
    else
        echo "No environment.yml, conda will not install any package."
    fi

    if [ -e "$_CONDOR_JOB_IWD/requirements.txt" ]; then
        echo "Pip: requirements.txt found. Installing packages."
        /opt/conda/bin/python -m pip install -r $_CONDOR_JOB_IWD/requirements.txt
    else
        echo "No requirements.txt, pip will not install any module."
    fi

    # CA certificate securely transferred from scheduler
    if [[ -f "$_CONDOR_JOB_IWD/ca.pem" ]]; then
        PATH_CA_FILE="$_CONDOR_JOB_IWD/ca.pem"
    fi

    # Host cert securely transferred from scheduler; userkey is concatenated
    # into the same file.
    if [[ -f "$_CONDOR_JOB_IWD/hostcert.pem" ]]; then
        FILE_CERT="$_CONDOR_JOB_IWD/hostcert.pem"
        FILE_KEY="$_CONDOR_JOB_IWD/hostcert.pem"
    fi

    # Build and exec the worker. Parsing/command construction lives in
    # worker-args.sh; see cc_build_worker_command for the dask/taskvine split.
    if [ ! -z "$_CONDOR_JOB_AD" ]; then
        echo "Print ClassAd:" 1>&2
        cat "$_CONDOR_JOB_AD" 1>&2

        if ! MISSING=$(cc_worker_validate "$_CONDOR_JOB_AD"); then
            echo "Error: cannot start worker -- ${MISSING}" 1>&2
            exit 1
        fi

        HTCONDOR_COMMAND=$(cc_build_worker_command "$_CONDOR_JOB_AD" "$@")
        echo "$HTCONDOR_COMMAND" 1>&2
        exec $HTCONDOR_COMMAND
    fi
else
    exec "$@"
fi