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

# If the job shipped the notebook's conda env (CoffeaCasaEnvTarball attribute,
# set by coffea_casa.env_pack), unpack it into $dest, install any shipped
# editable-package wheels, and point CC_WORKER_PYTHON at the env's python.
# Returns 0 with CC_WORKER_PYTHON unset when no env was shipped, non-zero if the
# shipped env can't be set up (the worker must not start in the wrong env).
cc_setup_shipped_env() {
    local ad_file=$1 iwd=$2 dest=$3 tarball wheels
    [ -f "$ad_file" ] || return 0
    tarball=$(ad_get "$ad_file" CoffeaCasaEnvTarball)
    _is_unset "$tarball" && return 0
    if [ ! -f "$iwd/$tarball" ]; then
        echo "Error: shipped env $tarball was not transferred to $iwd" 1>&2
        return 1
    fi
    echo "Unpacking shipped conda env $tarball into $dest" 1>&2
    mkdir -p "$dest" \
        && tar -xzf "$iwd/$tarball" -C "$dest" \
        && "$dest/bin/python" "$dest/bin/conda-unpack" || {
        echo "Error: could not unpack shipped env $tarball" 1>&2
        return 1
    }
    wheels="$iwd/cc-editable-wheels"
    if compgen -G "$wheels/*.whl" > /dev/null; then
        echo "Installing shipped editable-package wheels from $wheels" 1>&2
        "$dest/bin/python" -m pip install --no-deps --no-index --force-reinstall \
            "$wheels"/*.whl 1>&2 || {
            echo "Error: could not install shipped wheels from $wheels" 1>&2
            return 1
        }
    fi
    CC_WORKER_PYTHON="$dest/bin/python"
}

# If the job shipped local code (CoffeaCasaShippedPaths attribute: the
# comma-separated names of the ship_paths files/directories, transferred into
# the job directory $iwd), check they all arrived and put $iwd on PYTHONPATH so
# the worker imports them. Non-zero if any are missing.
cc_setup_shipped_paths() {
    local ad_file=$1 iwd=$2 names name missing=""
    local -a list
    [ -f "$ad_file" ] || return 0
    names=$(ad_get "$ad_file" CoffeaCasaShippedPaths)
    _is_unset "$names" && return 0
    IFS=, read -ra list <<< "$names"
    for name in "${list[@]}"; do
        [ -e "$iwd/$name" ] || missing="$missing $name"
    done
    if [ -n "$missing" ]; then
        echo "Error: shipped paths not transferred to $iwd:$missing" 1>&2
        return 1
    fi
    export PYTHONPATH="$iwd${PYTHONPATH:+:$PYTHONPATH}"
    echo "Shipped paths ($names) importable from $iwd" 1>&2
}

cc_build_worker_command() {
    local ad_file=$1
    local name cpus mem host port nannyc containerp sched
    name=$(cc_worker_name "$ad_file")
    cpus=$(cc_worker_cpus "$ad_file")
    mem=$(cc_worker_memory_limit "$ad_file")
    host=$(cc_worker_host "$ad_file")
    port=$(ad_get "$ad_file" dask_HostPort)
    nannyc=$(ad_get "$ad_file" nanny_ContainerPort)
    containerp=$(ad_get "$ad_file" dask_ContainerPort)
    sched=$(ad_get "$ad_file" DaskSchedulerAddress)

    # No forwarded host port -> the container port is what's reachable.
    _is_unset "$port"  && port=$containerp

    # No --nanny-contact-address: upstream distributed has no such option
    # (dask_worker exits 2), it only existed in a patched build.
    # CC_WORKER_PYTHON is set by cc_setup_shipped_env when an env was shipped.
    echo "${CC_WORKER_PYTHON:-${CONDA_DIR:-/usr/local}/bin/python} -m distributed.cli.dask_worker $sched \
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
--contact-address tls://$host:$port"
}