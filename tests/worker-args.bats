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

@test "host extracts the hostname from RemoteHost slot syntax" {
    write_ad 'RemoteHost = "slot1_3@node42.af.uchicago.edu"'
    run cc_worker_host "$AD"
    [ "$output" = "node42.af.uchicago.edu" ]
}

# --- validation -------------------------------------------------------------

@test "validate passes when all networking attributes are present" {
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

@test "validate fails and reports the missing attributes" {
    write_ad 'dask_HostPort = 8786'
    run cc_worker_validate "$AD"
    [ "$status" -eq 1 ]
    [[ "$output" == *RemoteHost* ]]
    [[ "$output" == *DaskSchedulerAddress* ]]
    [[ "$output" != *dask_HostPort* ]]
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
    [[ "$output" == *"--contact-address tls://node42.af.uchicago.edu:8786"* ]]
    [[ "$output" == *"--nanny-contact-address tls://node42.af.uchicago.edu:8788"* ]]
    [[ "$output" == *"--listen-address tls://0.0.0.0:8787"* ]]
}

@test "build_worker_command applies all fallbacks for a minimal ad" {
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
