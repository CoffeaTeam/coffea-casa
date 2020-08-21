"""CoffeaCasaCluster class
"""
import os
import sys
from pathlib import Path
import dask
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob
from distributed.security import Security

# Port settings
DEFAULT_SCHEDULER_PORT = 8787
DEFAULT_DASHBOARD_PORT = 8786
DEFAULT_CONTAINER_PORT = 8787

# Security settings for Dask scheduler
SECRETS_DIR = Path('/etc/cmsaf-secrets')
CA_FILE = SECRETS_DIR / "ca.pem"
CERT_FILE = SECRETS_DIR / "hostcert.pem"
# XCache
XCACHE_FILE = SECRETS_DIR / "xcache_token"


def merge_dicts(*dict_args):
    """
    Given any number of dictionaries, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dictionaries.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


class CoffeaCasaJob(HTCondorJob):
    """
    """
    submit_command = "condor_submit -spool"
    config_name = "coffea-casa"


class CoffeaCasaCluster(HTCondorCluster):
    job_cls = CoffeaCasaJob
    config_name = "coffea-casa"

    def __init__(self,
                 *,
                 security=None,
                 worker_image=None,
                 scheduler_options=None,
                 scheduler_port=DEFAULT_SCHEDULER_PORT,
                 dashboard_port=DEFAULT_DASHBOARD_PORT,
                 **job_kwargs
                 ):
        """
        Parameters
        ----------
        worker_image
            Defaults to ``coffeateam/coffea-casa-analysis``
            (https://hub.docker.com/r/coffeateam/coffea-casa-analysis).
        scheduler_port
        dashboard_port
        job_kwargs
        """
        if security:
            self.security = security
        job_kwargs = self._modify_job_kwargs(
            job_kwargs,
            security=security,
            worker_image=worker_image,
            scheduler_port=scheduler_port,
            dashboard_port=dashboard_port,
        )
        # Instantiate args and parameters from parent abstract class security=security
        super().__init__(**job_kwargs)

    @classmethod
    def _modify_job_kwargs(cls,
                           job_kwargs,
                           *,
                           security=None,
                           worker_image=None,
                           scheduler_options=None,
                           scheduler_port=DEFAULT_SCHEDULER_PORT,
                           dashboard_port=DEFAULT_DASHBOARD_PORT,
                           ):
        job_config = job_kwargs.copy()
        # If we have ready security object lets try to use TLS
        #security.get_connection_args("scheduler").get("require_encryption") is True
        if security and security.get_connection_args("scheduler")['require_encryption']:
            job_config["protocol"] = 'tls://'
            job_config["security"] = security
            # We hope we have files locally and it should be used
            # for local tests only for now.
            files = ""
        # If we have certs in env lets try to use TLS
        elif CA_FILE.is_file() and CERT_FILE.is_file() and cls.security().get_connection_args("scheduler")['require_encryption']:
            job_config["protocol"] = 'tls://'
            job_config["security"] = cls.security()
            input_files = [CA_FILE, CERT_FILE, XCACHE_FILE]
            files = ", ".join(str(path) for path in input_files)
        else:
            job_config["protocol"] = 'tcp://'
            input_files = [XCACHE_FILE]
            files = ", ".join(str(path) for path in input_files)
        ## Networking settings
        try:
            external_ip = os.environ['HOST_IP']
        except KeyError:
            print("Please check with system administarator why external IP was not assigned for you.")
            sys.exit(1)
        if external_ip:
            address_list = [external_ip, DEFAULT_SCHEDULER_PORT]
            external_address_short = ":".join(str(item) for item in address_list)
            ###
            full_address_list = [job_config["protocol"], external_address_short]
            external_address = "".join(str(item) for item in full_address_list)
            external_ip_string = '"' + external_address + '"'
        ## Scheduler settings
        # we need to pass and check protocol for scheduler
        # (format should be not 'tls://'' but 'tls')
        scheduler_protocol = job_config["protocol"]
        job_config["scheduler_options"] = merge_dicts(
            {
                "port": scheduler_port,
                "dashboard_address": str(dashboard_port),
                "protocol": scheduler_protocol.replace("://",""),
                "external_address": external_address_short,
            },
            job_kwargs.get(
                "scheduler_options",
                dask.config.get(f"jobqueue.{cls.config_name}.scheduler-options"),
            ),
        )
        ## Job extra settings (HTCondor ClassAd)
        job_config["job_extra"] = merge_dicts(
            {
                "universe": "docker",
                "docker_image": worker_image or dask.config.get(f"jobqueue.{cls.config_name}.worker-image"),
            },
            {
                "container_service_names": "dask",
                "dask_container_port": DEFAULT_CONTAINER_PORT,
            },
            {"transfer_input_files": files},
            {"encrypt_input_files": files},
            {"transfer_output_files": '""'},
            {"when_to_transfer_output": '"ON_EXIT"'},
            {"should_transfer_files": '"YES"'},
            {"Stream_Output": 'False'},
            {"Stream_Error": 'False'},
            {"+DaskSchedulerAddress": external_ip_string},
            job_kwargs.get("job_extra", dask.config.get(f"jobqueue.{cls.config_name}.job-extra")),
        )
        print(job_config)
        return job_config

    @classmethod
    def security(cls):
        """
        """
        ca_file = str(CA_FILE)
        cert_file = str(CERT_FILE)
        return Security(
            tls_ca_file=ca_file,
            tls_worker_cert=cert_file,
            tls_worker_key=cert_file,
            tls_client_cert=cert_file,
            tls_client_key=cert_file,
            tls_scheduler_cert=cert_file,
            tls_scheduler_key=cert_file,
            require_encryption=True,
        )
