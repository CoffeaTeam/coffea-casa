import os
import shutil
import sys

from dask.distributed import Client
from dask_jobqueue import HTCondorCluster
from distributed.security import Security


# Inspired by https://github.com/JoshKarpel/dask-at-chtc
def CoffeaCasaCluster(
    worker_image=None, external_ip=None, tls=False, scheduler_port=8787, dashboard_port=8786, autoscale=True, min_scale=5, max_scale=10):
    shutil.rmtree("logs", ignore_errors=True)

    if worker_image is None:
        worker_image = sys.argv[1]
        
    if external_ip is None:
        try:
            worker_image = os.environ['HOST_IP']
        except ValueError:
            worker_image = sys.argv[2]

    external_address = str(external_ip)+':'+str(scheduler_port)
    external_ip_string = '"'+ external_address+'"'
    
    job_extra = {
        "universe": "docker",
        "docker_image": worker_image, 
        "container_service_names": "dask",
        "dask_container_port": "8787",
        "should_transfer_files": "YES",
        "when_to_transfer_output": "ON_EXIT",
        "+DaskSchedulerAddress": external_ip_string,
    }
    
    protocol = "tcp"
    
    security_tls = None

    if tls:
        security_tls = Security(tls_ca_file='/etc/cmsaf-secrets/ca.pem',
               tls_worker_cert='/etc/cmsaf-secrets/hostcert.pem',
               tls_worker_key='/etc/cmsaf-secrets/hostcert.pem',
               tls_client_cert='/etc/cmsaf-secrets/hostcert.pem',
               tls_client_key='/etc/cmsaf-secrets/hostcert.pem',
               tls_scheduler_cert='/etc/cmsaf-secrets/hostcert.pem',
               tls_scheduler_key='/etc/cmsaf-secrets/hostcert.pem',
               require_encryption=True
               )    
        protocol = "tls"
        external_address = 'tls://'+str(external_ip)+':'+str(scheduler_port)
        job_extra.update(
            {
                "transfer_input_files": "/etc/cmsaf-secrets/xcache_token,/etc/cmsaf-secrets/ca.pem,/etc/cmsaf-secrets/hostcert.pem",
                "encrypt_input_files": "/etc/cmsaf-secrets/xcache_token,/etc/cmsaf-secrets/ca.pem,/etc/cmsaf-secrets/hostcert.pem",
            }
        )
        
    else:
        job_extra.update(
            {
                "transfer_input_files": "/etc/cmsaf-secrets/xcache_token",
                "encrypt_input_files": "/etc/cmsaf-secrets/xcache_token",
            }
        )

    cluster = HTCondorCluster(
        cores=4,
        memory="6GB",
        disk="5GB",
        log_directory="logs",
        silence_logs="DEBUG",
        security = security_tls,
        env_extra=["LD_LIBRARY_PATH=/opt/conda/lib/", "XCACHE_HOST=red-xcache1.unl.edu", "XRD_PLUGIN=/opt/conda/lib/libXrdClAuthzPlugin.so", "BEARER_TOKEN_FILE=xcache_token"],
        scheduler_options={
            "protocol": protocol,
            "dashboard_address": str(dashboard_port),
            "port": scheduler_port,
            "external_address": external_address,
        },
        job_extra=job_extra,
        #extra=["--listen-address", "tcp://0.0.0.0:8787"],
    )
    
    if autoscale:
        cluster.adapt(minimum_jobs=min_scale, maximum_jobs=max_scale)  # auto-scale between min_scale and max_scale jobs
    else:
        cluster.scale(max_scale)
    
    if tls:
        client = Client(cluster, security=security_tls)
    else:
        client = Client(cluster)

    return client
