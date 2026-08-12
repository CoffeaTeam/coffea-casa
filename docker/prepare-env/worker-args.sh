#!/bin/bash
# Pure helpers for deriving dask-worker arguments from an HTCondor job ClassAd.
# Drop-in replacement. Changes vs upstream:
#   * host is taken from StartdIpAddr (as in the known-good cc8fa51), not RemoteHost
#   * *_HostPort is NOT required; if empty/"undefined" we fall back to the
#     container port (correct under host networking, and safe once the real
#     forwarded port is present because the entrypoint now waits for it).

ad_get() {
    sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | tr -d '"' | tail -n1
}

# Empty OR the literal string "undefined" both mean "no usable value".
_is_unset() { [ -z "$1" ] || [ "$1" = "undefined" ]; }

cc_worker_cpus() { local c; c=$(ad_get "$1" DaskWorkerCores); echo "${c:-1}"; }

cc_worker_name() {
    local name; name=$(ad_get "$1" DaskWorkerName)
    [ -z "$name" ] && name="dask-worker-$(hostname)-$$"
    echo "$name"
}

cc_worker_memory_limit() {
    local bytes mb
    bytes=$(ad_get "$1" DaskWorkerMemory)
    if [ -n "$bytes" ]; then echo "$bytes"; return 0; fi
    mb=$(ad_get "$1" RequestMemory); echo "${mb:-2048}MB"
}

# Advertise the startd's IP (known-good behavior), fall back to RemoteHost host part.
cc_worker_host() {
    local ip
    ip=$(sed -n 's/.*StartdIpAddr = "<\([^:]*\).*/\1/p' "$1" | tail -n1)
    _is_unset "$ip" && ip=$(ad_get "$1" RemoteHost | tr '@' ' ' | awk '{print $NF}')
    echo "$ip"
}

# Only the attributes the worker truly cannot start without. HostPort is optional.
cc_worker_validate() {
    local ad_file=$1 missing="" v val
    for v in dask_ContainerPort nanny_ContainerPort DaskSchedulerAddress; do
        val=$(ad_get "$ad_file" "$v"); _is_unset "$val" && missing="$missing $v"
    done
    val=$(cc_worker_host "$ad_file"); _is_unset "$val" && missing="$missing host"
    [ -n "$missing" ] && { echo "missing:$missing"; return 1; }
    return 0
}

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

    # No forwarded host port -> the container port is what's reachable.
    _is_unset "$port"  && port=$containerp
    _is_unset "$nanny" && nanny=$nannyc

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