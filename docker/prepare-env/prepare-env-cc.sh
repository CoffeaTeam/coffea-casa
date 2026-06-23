#!/bin/bash
set -x

# Read a single ClassAd attribute value from the job ad file.
# Anchors on "<attr> = " at line start, strips quotes, returns the last match.
# More robust than `grep <attr> | awk '{print $NF}'`, which relies on field
# position and trailing-space tricks to avoid prefix collisions.
ad() {
    sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$_CONDOR_JOB_AD" \
        | tr -d '"' | tail -n1
}

if [ "$EXTRA_CONDA_PACKAGES" ]; then
    echo "conda: EXTRA_CONDA_PACKAGES environment variable found. Installing."
    /opt/conda/bin/mamba install -y $EXTRA_CONDA_PACKAGES
fi

if [ "$EXTRA_PIP_PACKAGES" ]; then
    echo "pip: EXTRA_PIP_PACKAGES environment variable found. Installing"
    /opt/conda/bin/pip install $EXTRA_PIP_PACKAGES
fi

# FIXME: in case of sidecar dask worker is available
if [[ "$SKYHOOK_CEPH_KEYRING" && "$SKYHOOK_CEPH_UUIDGEN" && "$SKYHOOK_CLUSTER_ADDR" && "$SKYHOOK_PUBLIC_ADDR" && "$SKYHOOK_MON_HOST" ]]; then
    sed -i -e "s|%(SKYHOOK_CEPH_UUIDGEN)|${SKYHOOK_CEPH_UUIDGEN}|g" $CEPH_DIR/ceph.conf
    sed -i -e "s|%(SKYHOOK_CEPH_KEYRING)|${SKYHOOK_CEPH_KEYRING}|g" $CEPH_DIR/keyring
    sed -i -e "s|%(SKYHOOK_MON_HOST)|${SKYHOOK_MON_HOST}|g" $CEPH_DIR/ceph.conf
    sed -i -e "s|%(SKYHOOK_PUBLIC_ADDR)|${SKYHOOK_PUBLIC_ADDR}|g" $CEPH_DIR/ceph.conf
    sed -i -e "s|%(SKYHOOK_CLUSTER_ADDR)|${SKYHOOK_CLUSTER_ADDR}|g" $CEPH_DIR/ceph.conf
    # Testing ceph status
    # Remove check for now since AGC ceph setup is not responding...
    #ceph -s
else
    echo "Skyhook was not configured. Please add next env values: SKYHOOK_CEPH_KEYRING SKYHOOK_CEPH_UUIDGEN SKYHOOK_CLUSTER_ADDR SKYHOOK_PUBLIC_ADDR SKYHOOK_MON_HOST in helm charts."
fi

# If there is defined COFFEA_CASA_SIDECAR env variable (inside hub values.yml),
# then we use this container as a sidecar for notebook.
if [[ ! -v COFFEA_CASA_SIDECAR ]]; then
    if [ "${GITHUB_ACTIONS:-}" == "true" ]; then
        echo "CI mode, no need to test dask_HostPort info..."
    else
        # From chtc/dask-chtc: wait for the job ad to be updated with <service>_HostPort
        # This happens during the first update, usually a few seconds after the job starts
        echo "Waiting for dask_HostPort and nanny_HostPort information..."
        # Check if we are not in GH CI environment (otherwise image check will stuck forever)
        # docs: Always set to true when GitHub Actions is running the workflow.
        # You can use this variable to differentiate when tests are being run locally or by GitHub Actions.
        while true; do
            if grep dask_HostPort "$_CONDOR_JOB_AD"; then
                break
            fi
            sleep 1
        done
        echo "Got dask_HostPort, proceeding..."
        echo
        while true; do
            if grep nanny_HostPort "$_CONDOR_JOB_AD"; then
                break
            fi
            sleep 1
        done
        echo "Got nanny_HostPort, proceeding..."
        echo
        if [ -z "$_CONDOR_JOB_IWD" ]; then
            echo "Error: something is wrong, $_CONDOR_JOB_IWD (path to the initial working directory the job was born with) was not defined!"
            exit 1
        fi
    fi

    # Condor token securily transfered from scheduler
    if [[ -f "$_CONDOR_JOB_IWD/condor_token" ]]; then
        mkdir -p /home/$NB_USER/.condor/tokens.d/ && cp $_CONDOR_JOB_IWD/condor_token /home/$NB_USER/.condor/tokens.d/condor_token
    fi

    if [[ -f "$_CONDOR_JOB_IWD/ceph.conf" ]]; then
        cp $_CONDOR_JOB_IWD/ceph.conf ${CEPH_DIR}
    fi

    if [[ -f "$_CONDOR_JOB_IWD/access_token" ]]; then
        mkdir -p /home/$NB_USER/.xcache && cp $_CONDOR_JOB_IWD/access_token /home/$NB_USER/.xcache/access_token
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

    # CA certificate securily transfered from scheduler
    if [[ -f "$_CONDOR_JOB_IWD/ca.pem" ]]; then
        PATH_CA_FILE="$_CONDOR_JOB_IWD/ca.pem"
    fi

    # Hostcertn securily transfered from scheduler and
    # userkey here is simply concatenated in usercert
    if [[ -f "$_CONDOR_JOB_IWD/hostcert.pem" ]]; then
        FILE_CERT="$_CONDOR_JOB_IWD/hostcert.pem"
        FILE_KEY="$_CONDOR_JOB_IWD/hostcert.pem"
    fi

    # HTCondor port, hostname and external IP ("must" variables)
    if [ ! -z "$_CONDOR_JOB_AD" ]; then
        # We make sure that we use proper configuration (dask worker name, ports,
        # number of CPUs, memory requested for worker, hostname of scheduler),
        # parsing the HTCondor job ClassAd file via the ad() helper above.

        # --- Networking attributes (worker cannot start without these) ---
        PORT=$(ad dask_HostPort)
        NANNYPORT=$(ad nanny_HostPort)
        NANNYCONTAINER_PORT=$(ad nanny_ContainerPort)
        CONTAINER_PORT=$(ad dask_ContainerPort)
        # Requirement: add to the Condor job description e.g.
        #   "+DaskSchedulerAddress": '"tcp://129.93.183.34:8787"'
        EXTERNALIP_PORT=$(ad DaskSchedulerAddress)
        # RemoteHost looks like "slot1_1@node.example.com" -> take the host part
        HOST=$(ad RemoteHost | tr '@' ' ' | awk '{print $NF}')

        # --- Worker sizing attributes (have safe fallbacks) ---
        NAME=$(ad DaskWorkerName)
        CPUS=$(ad DaskWorkerCores)
        : "${CPUS:=1}"
        [ -n "$NAME" ] || NAME="dask-worker-$(hostname)-$$"

        # Memory: prefer DaskWorkerMemory (bytes, set by dask-jobqueue's
        # HTCondorCluster), which dask-worker accepts directly. Fall back to
        # RequestMemory (MB) only if the dask-specific attribute is absent.
        MEMORY_BYTES=$(ad DaskWorkerMemory)
        if [ -n "$MEMORY_BYTES" ]; then
            MEMORY_LIMIT="$MEMORY_BYTES"
        else
            MEMORY_MB=$(ad RequestMemory)
            : "${MEMORY_MB:=2048}"
            MEMORY_LIMIT="${MEMORY_MB}MB"
        fi

        # --- Fail fast if any required networking value is missing ---
        for v in PORT NANNYPORT NANNYCONTAINER_PORT CONTAINER_PORT HOST EXTERNALIP_PORT; do
            if [ -z "${!v}" ]; then
                echo "Error: required ClassAd value '$v' is empty; cannot start dask-worker." 1>&2
                echo "Dumping job ClassAd for debugging:" 1>&2
                cat "$_CONDOR_JOB_AD" 1>&2
                exit 1
            fi
        done

        echo "Print ClassAd:" 1>&2
        cat "$_CONDOR_JOB_AD" 1>&2

        # Dask worker command executed in the HTCondor pool.
        # Communication protocol: in coffea-casa we use only secured
        # communications (over TLS).
        HTCONDOR_COMAND="/opt/conda/bin/python -m distributed.cli.dask_worker $EXTERNALIP_PORT \
            --name $NAME \
            --tls-ca-file $PATH_CA_FILE \
            --tls-cert $FILE_CERT \
            --tls-key $FILE_KEY \
            --nthreads $CPUS \
            --memory-limit $MEMORY_LIMIT \
            --nanny \
            --nanny-port $NANNYCONTAINER_PORT \
            --death-timeout 60 \
            --protocol tls \
            --lifetime 7200 \
            --listen-address tls://0.0.0.0:$CONTAINER_PORT \
            --nanny-contact-address tls://$HOST:$NANNYPORT \
            --contact-address tls://$HOST:$PORT"

        # Debug print
        echo "$HTCONDOR_COMAND" 1>&2

        exec $HTCONDOR_COMAND
    fi
else
    exec "$@"
fi