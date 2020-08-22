"""CoffeaCasaCluster method
"""
import os
import shutil
import sys

from dask.distributed import Client
from distributed.security import Security
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob


def coffea_casa_cluster(
        worker_image=None,
        external_ip=None,
        tls=False,
        scheduler_port=8786,
        dashboard_port=8787,
        autoscale=True,
        min_scale=5,
        max_scale=10, cores=4):
    """CoffeaCasaCluster method (to be replaced!)
    """
    shutil.rmtree("logs", ignore_errors=True)
    # Must arguments: worker_image and external_ip
    if worker_image is None:
        worker_image = sys.argv[1]

    try:
        external_ip = os.environ['HOST_IP']
    except KeyError:
        print("Please check with system administarator \
               why external IP was not assigned for you.")

    if external_ip is None:
        external_ip = sys.argv[2]

    # External IP to be used by scheduler
    external_address = str(external_ip) + ':' + str(scheduler_port)
    external_ip_string = '"' + external_address + '"'

    # Extra job parameters
    job_extra = {
        "universe": "docker",
        "docker_image": worker_image,
        "container_service_names": "dask",
        "dask_container_port": "8786",
        "should_transfer_files": "YES",
        "when_to_transfer_output": "ON_EXIT",
        "+DaskSchedulerAddress": external_ip_string,
    }

    # Default protocol is tcp, and Dask Security object is null
    protocol = "tcp"
    security_tls = None

    # If you want TLS, we will create a Dask Security object for you
    if tls:
        security_tls = Security(tls_ca_file='/etc/cmsaf-secrets/ca.pem',
                                tls_worker_cert='/etc/cmsaf-secrets/hostcert.pem',
                                tls_worker_key='/etc/cmsaf-secrets/hostcert.pem',
                                tls_client_cert='/etc/cmsaf-secrets/hostcert.pem',
                                tls_client_key='/etc/cmsaf-secrets/hostcert.pem',
                                tls_scheduler_cert='/etc/cmsaf-secrets/hostcert.pem',
                                tls_scheduler_key='/etc/cmsaf-secrets/hostcert.pem',
                                require_encryption=True)
        # Redefine protocol as TLS for now
        protocol = "tls"
        # Redefine address adding tls:// for Dask Scheduler
        external_address = 'tls://' + str(external_ip) + ':' + str(scheduler_port)
        job_extra.update(
            {
                "transfer_input_files": "/etc/cmsaf-secrets/xcache_token,/etc/cmsaf-secrets/ca.pem,/etc/cmsaf-secrets/hostcert.pem",
                "encrypt_input_files": "/etc/cmsaf-secrets/xcache_token,/etc/cmsaf-secrets/ca.pem,/etc/cmsaf-secrets/hostcert.pem",
            })
    else:
        job_extra.update(
            {
                "transfer_input_files": "/etc/cmsaf-secrets/xcache_token",
                "encrypt_input_files": "/etc/cmsaf-secrets/xcache_token",
            })

    # Extend a submit_command for HTCondorJobs
    HTCondorJob.submit_command = "condor_submit -spool"

    #
    cluster = HTCondorCluster(
        cores=cores,
        memory="6GB",
        disk="5GB",
        log_directory="logs",
        silence_logs="DEBUG",
        security=security_tls,
        env_extra=["LD_LIBRARY_PATH=/opt/conda/lib/",
                   "XCACHE_HOST=red-xcache1.unl.edu",
                   "XRD_PLUGIN=/opt/conda/lib/libXrdClAuthzPlugin.so",
                   "BEARER_TOKEN_FILE=xcache_token"],
        scheduler_options={
            "protocol": protocol,
            "dashboard_address": str(dashboard_port),
            "port": scheduler_port,
            "external_address": external_address,
        },
        job_extra=job_extra,
    )

    if autoscale:
        # auto-scale between min_scale and max_scale jobs
        cluster.adapt(minimum_jobs=min_scale, maximum_jobs=max_scale)
    else:
        # scale only up to maximum jobs
        cluster.scale(jobs=max_scale)

    if tls:
        client = Client(cluster, security=security_tls)
    else:
        client = Client(cluster)

    return client
