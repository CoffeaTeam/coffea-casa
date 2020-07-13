import os
import sys
from time import sleep, time

import dask
import pytest
from distributed import Client
from distributed.security import Security

from coffea_casa import CoffeaCasaCluster

os.environ["HOST_IP"] = "192.168.1.44"

def test_header():
    with CoffeaCasaCluster(cores=1, memory="100MB", disk="100MB", worker_image="coffeateam/coffea-casa:latest") as cluster:
        job_script = cluster.job_script()
        print(job_script)
        print(cluster.scheduler_spec)
        assert cluster._dummy_job.job_header_dict["MY.DaskWorkerCores"] == 1
        assert cluster._dummy_job.job_header_dict["MY.DaskWorkerDisk"] == 100000000
        assert cluster._dummy_job.job_header_dict["MY.DaskWorkerMemory"] == 100000000
        assert cluster._dummy_job.job_header_dict["docker_image"] == "coffeateam/coffea-casa:latest"
        

def test_job_script():
    with CoffeaCasaCluster(
        cores=4,
        processes=4,
        memory="500MB",
        disk="500MB",
        worker_image="coffeateam/coffea-casa:latest",
        env_extra=['export LANG="en_US.utf8"', 'export LC_ALL="en_US.utf8"'],
        job_extra={"+Extra": "True"},
    ) as cluster:
        job_script = cluster.job_script()
        print(cluster.scheduler_spec)
        print(job_script)
        assert "RequestCpus = MY.DaskWorkerCores" in job_script
        assert "RequestDisk = floor(MY.DaskWorkerDisk / 1024)" in job_script
        assert "RequestMemory = floor(MY.DaskWorkerMemory / 1048576)" in job_script
        assert "MY.DaskWorkerCores = 4" in job_script
        assert "MY.DaskWorkerDisk = 500000000" in job_script
        assert "MY.DaskWorkerMemory = 500000000" in job_script
        assert "docker_image = coffeateam/coffea-casa:latest" in job_script
        assert 'MY.JobId = "$(ClusterId).$(ProcId)"' in job_script
        assert "LANG=en_US.utf8" in job_script
        assert "LC_ALL=en_US.utf8" in job_script
        assert "export" not in job_script
        assert "+Extra = True" in job_script

        assert (
            "{} -m distributed.cli.dask_worker tcp://".format(sys.executable)
            in job_script
        )
        assert "--memory-limit 125.00MB" in job_script
        assert "--nthreads 1" in job_script
        assert "--nprocs 4" in job_script

   
def test_scheduler():
   with CoffeaCasaCluster(
        cores=1, memory="100MB", disk="100MB", worker_image="coffeateam/coffea-casa:latest", scheduler_options={
            #"protocol": protocol,
            "dashboard_address": 8786,
            "port": 8787,
            "external_address": "192.168.1.45:8787",}
    ) as cluster:
       print(cluster.scheduler_spec)
       expected = "'external_address': '192.168.1.45:8787'"
       assert expected in str(cluster.scheduler_spec)
       #cluster.scale(1)
       #assert expected in str(cluster.worker_spec)
        
        
def test_security():
    dirname = os.path.dirname(__file__)
    key = os.path.join(dirname, "key.pem")
    cert = os.path.join(dirname, "ca.pem")
    security = Security(
        tls_ca_file=cert,
        tls_scheduler_key=key,
        tls_scheduler_cert=cert,
        tls_worker_key=key,
        tls_worker_cert=cert,
        tls_client_key=key,
        tls_client_cert=cert,
        require_encryption=True,
    )

    with CoffeaCasaCluster(
        cores=1, memory="100MB", disk="100MB", worker_image="coffeateam/coffea-casa:latest", security=security, protocol="tls://"
    ) as cluster:
        print(cluster.scheduler_spec)
        assert cluster.security == security
        assert cluster.scheduler_spec["options"]["security"] == security
        job_script = cluster.job_script()
        print(job_script)
        # FIXME: Broken
        #assert "--tls-key {}".format(key) in job_script
        #assert "--tls-cert {}".format(cert) in job_script
        #assert "--tls-ca-file {}".format(cert) in job_script

        # FIXME: doesnt work locally
        #cluster.scale(jobs=1)
        #with Client(cluster, security=security) as client:
        #    future = client.submit(lambda x: x + 1, 10)
        #    result = future.result()
        #    assert result == 11
