import os
import sys
import socket
import pytest
from distributed.security import Security
from distributed import Client
from coffea_casa import CoffeaCasaCluster

os.environ["HOST_IP"] = socket.gethostbyname(socket.gethostname())

@pytest.mark.skip(reason="TLS is still not working with custom Security object")
def test_header():
    with CoffeaCasaCluster(cores=1,
                           memory="100MB",
                           disk="100MB",
                           worker_image="coffeateam/coffea-casa-analysis:0.2.26",
                           scheduler_options={'protocol': 'tls'}
                           ) as cluster:
        job_script = cluster.job_script()
        print("HTCondor Job script:", job_script)
        print("Scheduler specs:", cluster.scheduler_spec)
        kwargs = CoffeaCasaCluster._modify_job_kwargs({})
        print("CoffeaCasaCluster arguments:", kwargs)
        assert cluster._dummy_job.job_header_dict["MY.DaskWorkerCores"] == 1
        assert cluster._dummy_job.job_header_dict["MY.DaskWorkerDisk"] == 100000000
        assert cluster._dummy_job.job_header_dict["MY.DaskWorkerMemory"] == 100000000

@pytest.mark.skip(reason="TLS is still not working with custom Security object")
def test_job_script():
    with CoffeaCasaCluster(cores=4,
                           processes=4,
                           memory="500MB",
                           disk="500MB",
                           worker_image="coffeateam/coffea-casa-analysis:0.2.26",
                           scheduler_options={'protocol': 'tls'},
                           env_extra=['export LANG="en_US.utf8"',
                                      'export LC_ALL="en_US.utf8"'],
                           job_extra={"+Extra": "True"},
                           ) as cluster:
        job_script = cluster.job_script()
        print("HTCondor Job script:", job_script)
        print("Scheduler specs:", cluster.scheduler_spec)
        assert "RequestCpus = MY.DaskWorkerCores" in job_script
        assert "RequestDisk = floor(MY.DaskWorkerDisk / 1024)" in job_script
        assert "RequestMemory = floor(MY.DaskWorkerMemory / 1048576)" in job_script
        assert "MY.DaskWorkerCores = 4" in job_script
        assert "MY.DaskWorkerDisk = 500000000" in job_script
        assert "MY.DaskWorkerMemory = 500000000" in job_script
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

@pytest.mark.skip(reason="TLS is still not working with custom Security object")
def test_scheduler():
    with CoffeaCasaCluster(cores=1,
                           memory="100MB",
                           disk="100MB",
                           worker_image="coffeateam/coffea-casa-analysis:0.2.26",
                           scheduler_options={
                               "dashboard_address": 8787,
                               "port": 8788,
                               "protocol": 'tls'}
                           ) as cluster:
        job_script = cluster.job_script()
        print("HTCondor Job script:", job_script)
        print("Scheduler specs:", cluster.scheduler_spec)
        kwargs = CoffeaCasaCluster._modify_job_kwargs({})
        print("CoffeaCasaCluster arguments:", kwargs)
        #assert cluster.scheduler_spec["port"] == 8788
        expected = os.environ["HOST_IP"]
        assert expected in str(cluster.scheduler_spec)
        #cluster.scale(1)
        #assert expected in str(cluster.worker_spec)

@pytest.mark.skip(reason="TLS is still not working with custom Security object")
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
    cluster = CoffeaCasaCluster(cores=1,
                                memory="100MB",
                                disk="100MB",
                                worker_image="coffeateam/coffea-casa-analysis:0.2.26",
                                security=security)
    assert security.get_connection_args("scheduler").get("require_encryption") is True
    job_script = cluster.job_script()
    print("HTCondor JobAd script:", job_script)
    print("Scheduler specs:", cluster.scheduler_spec)
    kwargs = CoffeaCasaCluster._modify_job_kwargs({})
    print("CoffeaCasaCluster arguments:", kwargs)
    assert cluster.security == security
    assert cluster.scheduler_spec["options"]["security"] == security
    assert "--tls-key {}".format(key) in job_script
    assert "--tls-cert {}".format(cert) in job_script
    assert "--tls-ca-file {}".format(cert) in job_script
    #cluster.scale(jobs=1)
    #with Client(cluster, security=security) as client:
    #    future = client.submit(lambda x: x + 1, 10)
    #    result = future.result()
    #    assert result == 11
