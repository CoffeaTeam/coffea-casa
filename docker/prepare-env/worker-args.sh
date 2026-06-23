#!/bin/bash
# Pure helpers for deriving dask-worker arguments from an HTCondor job ClassAd.
#
# Sourced by prepare-env-cc.sh. Kept separate so the parsing logic can
# be unit-tested in isolation, without running the full container entrypoint.
#
# Every function takes the ClassAd file path as its first argument and has no
# other side effects, so tests can drive them with fixture files.

# Read a single ClassAd attribute value.
#   $1 = path to job ClassAd file
#   $2 = attribute name
# Anchors on "<attr> = " at line start (no prefix collisions), strips quotes,
# and returns the last occurrence if the attribute appears more than once.
ad_get() {
    sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | tr -d '"' | tail -n1
}

# --nthreads value: DaskWorkerCores, default 1.
cc_worker_cpus() {
    local cpus
    cpus=$(ad_get "$1" DaskWorkerCores)
    echo "${cpus:-1}"
}

# --name value: DaskWorkerName, default dask-worker-<host>-<pid>.
cc_worker_name() {
    local name
    name=$(ad_get "$1" DaskWorkerName)
    if [ -z "$name" ]; then
        name="dask-worker-$(hostname)-$$"
    fi
    echo "$name"
}

# --memory-limit value: prefer DaskWorkerMemory (bytes, accepted directly by
# dask-worker), fall back to RequestMemory (MB), default 2048MB.
cc_worker_memory_limit() {
    local bytes mb
    bytes=$(ad_get "$1" DaskWorkerMemory)
    if [ -n "$bytes" ]; then
        echo "$bytes"
        return 0
    fi
    mb=$(ad_get "$1" RequestMemory)
    echo "${mb:-2048}MB"
}

# Hostname from RemoteHost: "slot1_3@node.example.com" -> "node.example.com".
cc_worker_host() {
    ad_get "$1" RemoteHost | tr '@' ' ' | awk '{print $NF}'
}

# Validate that all networking attributes the worker cannot start without are
# present. On success: return 0. On failure: print "missing: <names>" and
# return 1.
cc_worker_validate() {
    local ad_file=$1 missing="" v val
    for v in dask_HostPort nanny_HostPort nanny_ContainerPort \
             dask_ContainerPort RemoteHost DaskSchedulerAddress; do
        val=$(ad_get "$ad_file" "$v")
        [ -z "$val" ] && missing="$missing $v"
    done
    if [ -n "$missing" ]; then
        echo "missing:$missing"
        return 1
    fi
    return 0
}

# Assemble the full dask-worker command from the ClassAd. Cert paths come from
# the environment (PATH_CA_FILE / FILE_CERT / FILE_KEY), as in the entrypoint.
cc_build_worker_command() {
    local ad_file=$1
    local name cpus mem host port nanny nannyc containerp sched
    name=$(cc_worker_name "$ad_file")
    cpus=$(cc_worker_cpus "$ad_file")
    mem=$(cc_worker_memory_limit "$ad_file")
    host=$(cc_worker_host "$ad_file")
    port=$(ad_get "$ad_file" dask_HostPort)
    nanny=$(ad_get "$ad_file" nanny_HostPort)
    nannyc=$(ad_get "$ad_file" nanny_ContainerPort)
    containerp=$(ad_get "$ad_file" dask_ContainerPort)
    sched=$(ad_get "$ad_file" DaskSchedulerAddress)

    echo "/opt/conda/bin/python -m distributed.cli.dask_worker $sched \
--name $name \
--tls-ca-file ${PATH_CA_FILE:-} \
--tls-cert ${FILE_CERT:-} \
--tls-key ${FILE_KEY:-} \
--nthreads $cpus \
--memory-limit $mem \
--nanny \
--nanny-port $nannyc \
--death-timeout 60 \
--protocol tls \
--lifetime 7200 \
--listen-address tls://0.0.0.0:$containerp \
--nanny-contact-address tls://$host:$nanny \
--contact-address tls://$host:$port"
}