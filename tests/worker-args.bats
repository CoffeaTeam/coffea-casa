#!/usr/bin/env bats
#
# Tests for docker/prepare-env/worker-args.sh
# Run locally with: bats worker-args.bats

setup() {
    # Test lives in tests/; the library under test lives in docker/prepare-env/.
    # Resolve the repo root from this file's location so the suite works from
    # any cwd. Override LIB_UNDER_TEST to point elsewhere if your layout differs.
    REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/.." && pwd)"
    LIB_UNDER_TEST="${LIB_UNDER_TEST:-${REPO_ROOT}/docker/prepare-env/worker-args.sh}"
    # shellcheck source=/dev/null
    source "$LIB_UNDER_TEST"
    AD="$BATS_TEST_TMPDIR/job.ad"
}

# Write one ClassAd line per argument.
write_ad() {
    printf '%s\n' "$@" > "$AD"
}

# --- ad_get: the parsing primitive -----------------------------------------

@test "ad_get reads a simple integer attribute" {
    write_ad 'DaskWorkerCores = 8'
    run ad_get "$AD" DaskWorkerCores
    [ "$status" -eq 0 ]
    [ "$output" = "8" ]
}

@test "ad_get strips surrounding quotes" {
    write_ad 'DaskWorkerName = "worker-xyz"'
    run ad_get "$AD" DaskWorkerName
    [ "$output" = "worker-xyz" ]
}

@test "ad_get is anchored: no prefix collision" {
    # The old grep approach could match OriginalRequestMemory when asked for
    # RequestMemory. Anchoring on line start prevents that.
    write_ad 'OriginalRequestMemory = 9999' 'RequestMemory = 2048'
    run ad_get "$AD" RequestMemory
    [ "$output" = "2048" ]
}

@test "ad_get tolerates extra whitespace around the equals sign" {
    write_ad '   DaskWorkerCores    =    12'
    run ad_get "$AD" DaskWorkerCores
    [ "$output" = "12" ]
}

@test "ad_get returns empty for a missing attribute" {
    write_ad 'DaskWorkerCores = 4'
    run ad_get "$AD" DoesNotExist
    [ "$output" = "" ]
}

@test "ad_get returns the last value when an attribute is duplicated" {
    write_ad 'DaskWorkerCores = 4' 'DaskWorkerCores = 8'
    run ad_get "$AD" DaskWorkerCores
    [ "$output" = "8" ]
}

# --- _is_unset: empty or the literal "undefined" ---------------------------

@test "_is_unset is true for empty and for the literal 'undefined'" {
    run _is_unset ""
    [ "$status" -eq 0 ]
    run _is_unset "undefined"
    [ "$status" -eq 0 ]
}

@test "_is_unset is false for a real value" {
    run _is_unset "8786"
    [ "$status" -eq 1 ]
}

# --- cores ------------------------------------------------------------------

@test "cpus uses DaskWorkerCores when present" {
    write_ad 'DaskWorkerCores = 16'
    run cc_worker_cpus "$AD"
    [ "$output" = "16" ]
}

@test "cpus falls back to 1 when absent" {
    write_ad 'RequestMemory = 2048'
    run cc_worker_cpus "$AD"
    [ "$output" = "1" ]
}

# --- name -------------------------------------------------------------------

@test "name uses DaskWorkerName when present" {
    write_ad 'DaskWorkerName = "htcondor--12345.0--"'
    run cc_worker_name "$AD"
    [ "$output" = "htcondor--12345.0--" ]
}

@test "name falls back to a generated value when absent" {
    write_ad 'DaskWorkerCores = 4'
    run cc_worker_name "$AD"
    [[ "$output" == dask-worker-* ]]
}

# --- memory -----------------------------------------------------------------

@test "memory prefers DaskWorkerMemory (bytes), passed through verbatim" {
    write_ad 'DaskWorkerMemory = 2147483648' 'RequestMemory = 2048'
    run cc_worker_memory_limit "$AD"
    [ "$output" = "2147483648" ]
}

@test "memory falls back to RequestMemory with an MB suffix" {
    write_ad 'RequestMemory = 4096'
    run cc_worker_memory_limit "$AD"
    [ "$output" = "4096MB" ]
}

@test "memory defaults to 2048MB when nothing is present" {
    write_ad 'DaskWorkerCores = 4'
    run cc_worker_memory_limit "$AD"
    [ "$output" = "2048MB" ]
}

# --- host -------------------------------------------------------------------
# The worker advertises the startd's IP (as in the known-good cc8fa51), and
# only falls back to the RemoteHost hostname when StartdIpAddr is unavailable.

@test "host prefers StartdIpAddr when present" {
    write_ad \
        'StartdIpAddr = "<129.93.183.34:9618?addrs=129.93.183.34-9618&noUDP>"' \
        'RemoteHost = "slot1_3@node42.af.uchicago.edu"'
    run cc_worker_host "$AD"
    [ "$output" = "129.93.183.34" ]
}

@test "host falls back to the RemoteHost hostname when StartdIpAddr is absent" {
    write_ad 'RemoteHost = "slot1_3@node42.af.uchicago.edu"'
    run cc_worker_host "$AD"
    [ "$output" = "node42.af.uchicago.edu" ]
}

# --- validation -------------------------------------------------------------
# *_HostPort is intentionally NOT required: it may be undefined, in which case
# the build falls back to the container port. Validation covers the attributes
# the worker genuinely cannot start without.

@test "validate passes when the required attributes are present" {
    write_ad \
        'dask_HostPort = 8786' \
        'nanny_HostPort = 8788' \
        'nanny_ContainerPort = 8789' \
        'dask_ContainerPort = 8787' \
        'RemoteHost = "slot1@node1"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'
    run cc_worker_validate "$AD"
    [ "$status" -eq 0 ]
}

@test "validate does NOT require *_HostPort (fallback handles it)" {
    # No dask_HostPort / nanny_HostPort at all -> still valid.
    write_ad \
        'nanny_ContainerPort = 8789' \
        'dask_ContainerPort = 8787' \
        'StartdIpAddr = "<10.0.0.7:9618>"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'
    run cc_worker_validate "$AD"
    [ "$status" -eq 0 ]
}

@test "validate fails and reports the missing attributes" {
    write_ad 'dask_HostPort = 8786'
    run cc_worker_validate "$AD"
    [ "$status" -eq 1 ]
    [[ "$output" == *dask_ContainerPort* ]]
    [[ "$output" == *nanny_ContainerPort* ]]
    [[ "$output" == *DaskSchedulerAddress* ]]
    [[ "$output" == *host* ]]
    # HostPort is not part of the required set.
    [[ "$output" != *dask_HostPort* ]]
}

@test "validate treats the literal 'undefined' as missing" {
    write_ad \
        'dask_ContainerPort = undefined' \
        'nanny_ContainerPort = 8789' \
        'StartdIpAddr = "<10.0.0.7:9618>"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'
    run cc_worker_validate "$AD"
    [ "$status" -eq 1 ]
    [[ "$output" == *dask_ContainerPort* ]]
}

# --- full command assembly --------------------------------------------------

@test "build_worker_command wires the parsed values into the right flags" {
    write_ad \
        'dask_HostPort = 8786' \
        'nanny_HostPort = 8788' \
        'nanny_ContainerPort = 8789' \
        'dask_ContainerPort = 8787' \
        'RemoteHost = "slot1_3@node42.af.uchicago.edu"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"' \
        'DaskWorkerName = "htcondor--12345.0--"' \
        'DaskWorkerCores = 8' \
        'DaskWorkerMemory = 2147483648'

    PATH_CA_FILE=/tmp/ca.pem FILE_CERT=/tmp/host.pem FILE_KEY=/tmp/host.pem \
        run cc_build_worker_command "$AD"

    [ "$status" -eq 0 ]
    [[ "$output" == *"--nthreads 8"* ]]
    [[ "$output" == *"--memory-limit 2147483648"* ]]
    [[ "$output" == *"--name htcondor--12345.0--"* ]]
    # No StartdIpAddr here -> host falls back to the RemoteHost hostname.
    [[ "$output" == *"--contact-address tls://node42.af.uchicago.edu:8786"* ]]
    [[ "$output" != *"--nanny-contact-address"* ]]
    [[ "$output" == *"--listen-address tls://0.0.0.0:8787"* ]]
}

@test "build_worker_command prefers StartdIpAddr for the contact host" {
    write_ad \
        'dask_HostPort = 8786' \
        'nanny_HostPort = 8788' \
        'nanny_ContainerPort = 8789' \
        'dask_ContainerPort = 8787' \
        'StartdIpAddr = "<129.93.183.34:9618?addrs=129.93.183.34-9618>"' \
        'RemoteHost = "slot1_3@node42.af.uchicago.edu"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'

    run cc_build_worker_command "$AD"
    [ "$status" -eq 0 ]
    [[ "$output" == *"--contact-address tls://129.93.183.34:8786"* ]]
    [[ "$output" != *"--nanny-contact-address"* ]]
}

@test "build falls back to the container ports when *_HostPort is undefined" {
    # This is the regression the fix targets: HTCondor left *_HostPort as the
    # literal 'undefined', which must NOT end up in the contact address.
    write_ad \
        'dask_HostPort = undefined' \
        'nanny_HostPort = undefined' \
        'nanny_ContainerPort = 8001' \
        'dask_ContainerPort = 8786' \
        'StartdIpAddr = "<10.0.0.7:9618>"' \
        'RemoteHost = "slot1@node1"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'

    run cc_build_worker_command "$AD"
    [ "$status" -eq 0 ]
    [[ "$output" == *"--contact-address tls://10.0.0.7:8786"* ]]
    [[ "$output" != *"--nanny-contact-address"* ]]
    [[ "$output" == *"--listen-address tls://0.0.0.0:8786"* ]]
    # The literal "undefined" must never appear as a port.
    [[ "$output" != *":undefined"* ]]
}

@test "build_worker_command applies name/cpu/memory fallbacks for a minimal ad" {
    write_ad \
        'dask_HostPort = 8786' \
        'nanny_HostPort = 8788' \
        'nanny_ContainerPort = 8789' \
        'dask_ContainerPort = 8787' \
        'RemoteHost = "slot1@node1"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'

    run cc_build_worker_command "$AD"
    [ "$status" -eq 0 ]
    [[ "$output" == *"--nthreads 1"* ]]
    [[ "$output" == *"--memory-limit 2048MB"* ]]
    [[ "$output" == *"--name dask-worker-"* ]]
}

# --- cc_setup_shipped_env: notebook conda env shipped with the job ----------

# A fake packed env: bin/python logs its arguments, conda-unpack is a no-op.
make_env_tarball() {
    local src="$BATS_TEST_TMPDIR/envsrc"
    mkdir -p "$src/bin" "$IWD"
    printf '#!/bin/sh\necho "$@" >> "$(dirname "$0")/../python.log"\n' > "$src/bin/python"
    printf '' > "$src/bin/conda-unpack"
    chmod +x "$src/bin/python"
    tar -czf "$IWD/$1" -C "$src" .
}

@test "setup_shipped_env is a no-op without the tarball attribute" {
    write_ad 'DaskWorkerCores = 2'
    IWD="$BATS_TEST_TMPDIR/iwd"
    unset CC_WORKER_PYTHON
    cc_setup_shipped_env "$AD" "$IWD" "$BATS_TEST_TMPDIR/env"
    [ -z "${CC_WORKER_PYTHON:-}" ]
}

@test "setup_shipped_env is a no-op without a job ad" {
    unset CC_WORKER_PYTHON
    cc_setup_shipped_env "" "$BATS_TEST_TMPDIR/iwd" "$BATS_TEST_TMPDIR/env"
    [ -z "${CC_WORKER_PYTHON:-}" ]
}

@test "setup_shipped_env unpacks the env and selects its python" {
    IWD="$BATS_TEST_TMPDIR/iwd"
    make_env_tarball cc-env-foo-abc.tar.gz
    write_ad 'CoffeaCasaEnvTarball = "cc-env-foo-abc.tar.gz"'
    dest="$BATS_TEST_TMPDIR/env"

    cc_setup_shipped_env "$AD" "$IWD" "$dest"
    [ "$CC_WORKER_PYTHON" = "$dest/bin/python" ]
    # conda-unpack ran with the env's python; no wheels, so no pip
    [ "$(cat "$dest/python.log")" = "$dest/bin/conda-unpack" ]
}

@test "setup_shipped_env installs shipped editable wheels" {
    IWD="$BATS_TEST_TMPDIR/iwd"
    make_env_tarball cc-env-foo-abc.tar.gz
    mkdir -p "$IWD/cc-editable-wheels"
    touch "$IWD/cc-editable-wheels/myana-1.0-py3-none-any.whl"
    write_ad 'CoffeaCasaEnvTarball = "cc-env-foo-abc.tar.gz"'
    dest="$BATS_TEST_TMPDIR/env"

    cc_setup_shipped_env "$AD" "$IWD" "$dest"
    grep -q -- "-m pip install --no-deps --no-index --force-reinstall $IWD/cc-editable-wheels/myana-1.0-py3-none-any.whl" "$dest/python.log"
}

@test "setup_shipped_env fails when the tarball was not transferred" {
    write_ad 'CoffeaCasaEnvTarball = "cc-env-foo-abc.tar.gz"'
    run cc_setup_shipped_env "$AD" "$BATS_TEST_TMPDIR/iwd" "$BATS_TEST_TMPDIR/env"
    [ "$status" -ne 0 ]
    [[ "$output" == *"was not transferred"* ]]
}

@test "build_worker_command uses the shipped env's python" {
    write_ad \
        'nanny_ContainerPort = 8789' \
        'dask_ContainerPort = 8787' \
        'RemoteHost = "slot1@node1"' \
        'DaskSchedulerAddress = "tls://1.2.3.4:8786"'
    CC_WORKER_PYTHON=/scratch/cc-env/bin/python run cc_build_worker_command "$AD"
    [[ "$output" == "/scratch/cc-env/bin/python -m distributed.cli.dask_worker "* ]]
}

# --- cc_setup_shipped_paths: local code shipped with ship_paths -------------

@test "setup_shipped_paths is a no-op without the attribute" {
    write_ad 'DaskWorkerCores = 2'
    PYTHONPATH=/orig
    cc_setup_shipped_paths "$AD" "$BATS_TEST_TMPDIR/iwd"
    [ "$PYTHONPATH" = "/orig" ]
}

@test "setup_shipped_paths is a no-op without a job ad" {
    PYTHONPATH=/orig
    cc_setup_shipped_paths "" "$BATS_TEST_TMPDIR/iwd"
    [ "$PYTHONPATH" = "/orig" ]
}

@test "setup_shipped_paths puts the job dir first on PYTHONPATH" {
    iwd="$BATS_TEST_TMPDIR/iwd"
    mkdir -p "$iwd/myanalysis/sub"
    touch "$iwd/helpers.py"
    write_ad 'CoffeaCasaShippedPaths = "helpers.py,myanalysis"'

    unset PYTHONPATH
    cc_setup_shipped_paths "$AD" "$iwd"
    [ "$PYTHONPATH" = "$iwd" ]

    PYTHONPATH=/orig
    cc_setup_shipped_paths "$AD" "$iwd"
    [ "$PYTHONPATH" = "$iwd:/orig" ]
    # Exported, so the dask worker and nanny processes inherit it
    [ "$(bash -c 'echo $PYTHONPATH')" = "$iwd:/orig" ]
}

@test "setup_shipped_paths handles names with spaces" {
    iwd="$BATS_TEST_TMPDIR/iwd"
    mkdir -p "$iwd/my analysis"
    write_ad 'CoffeaCasaShippedPaths = "my analysis"'
    unset PYTHONPATH
    cc_setup_shipped_paths "$AD" "$iwd"
    [ "$PYTHONPATH" = "$iwd" ]
}

@test "setup_shipped_paths fails and names the paths that did not arrive" {
    iwd="$BATS_TEST_TMPDIR/iwd"
    mkdir -p "$iwd"
    touch "$iwd/helpers.py"
    write_ad 'CoffeaCasaShippedPaths = "helpers.py,myanalysis,other.py"'
    run cc_setup_shipped_paths "$AD" "$iwd"
    [ "$status" -ne 0 ]
    [[ "$output" == *"not transferred"*"myanalysis other.py"* ]]
}
