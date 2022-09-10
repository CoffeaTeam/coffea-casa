"""CoffeaCasaCluster class
"""
import os
import sys
from pathlib import Path
import dask
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob
from distributed.security import Security

# Port settings
DEFAULT_SCHEDULER_PORT = 8786
DEFAULT_DASHBOARD_PORT = 8787
DEFAULT_CONTAINER_PORT = 8786
#DEFAULT_NANNY_PORT = 8001

# Security settings for Dask scheduler
SECRETS_DIR = Path("/etc/cmsaf-secrets")
# CEPH (Skyhook)
CEPH_DIR = Path("/opt/ceph")
CEPH_CONF = CEPH_DIR / "ceph.conf"
KEYRING_CONF = CEPH_DIR / "keyring"
CA_FILE = SECRETS_DIR / "ca.pem"
CERT_FILE = SECRETS_DIR / "hostcert.pem"
HOME_DIR = Path.home()
# XCache
XCACHE_FILE = SECRETS_DIR / "xcache_token"
# pip
PIP_REQUIREMENTS = HOME_DIR / "requirements.txt"
# conda, with yml/yaml both supported
if (HOME_DIR / "environment.yaml").is_file():
    CONDA_ENV = HOME_DIR / "environment.yaml"
else:
    CONDA_ENV = HOME_DIR / "environment.yml"


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
    """
    This is a  subclass expanding settings for launch Dask via HTCondorCluster
    over HTCondor in US.CMS facility.
    """
    job_cls = CoffeaCasaJob
    config_name = "coffea-casa"

    def __init__(self,
                 *,
                 security=None,
                 worker_image=None,
                 scheduler_options=None,
                 scheduler_port=DEFAULT_SCHEDULER_PORT,
                 dashboard_port=DEFAULT_DASHBOARD_PORT,
                 #nanny_port=DEFAULT_NANNY_PORT,
                 **job_kwargs):
        """
        Parameters
        ----------
        worker_image:
            Defaults to ``coffeateam/coffea-casa-analysis``
            (https://hub.docker.com/r/coffeateam/coffea-casa-analysis).
            Check the default version of container in `~/.config/dask/jobqueue-coffea-casa.yaml` or
            `/etc/dask/jobqueue-coffea-casa.yaml`
        scheduler_port:
            Defaults to 8786.
        dashboard_port:
            Defaults to 8787.
        container_port:
            Defaults to 8786.
        nanny_port:
            Defaults to 8001.
        disk:
            Total amount of disk per job (defaults to 5 GiB).
        cores:
            Total number of cores per job (defaults to 4 cores).
        memory:
            Total amount of memory per job (defaults to 6 GB).
        scheduler_options : dict
            Extra scheduler options for the job (Dask specific).
        job_extra : dict
            Extra submit file attributes for the job (HTCondor specific).

        Examples
        --------
        >>> from coffea_casa import CoffeaCasaCluster
        >>> cluster = CoffeaCasaCluster()
        >>> cluster.scale(jobs=10)  # ask for 10 jobs
        >>> from dask.distributed import Client
        >>> client = Client(cluster)
        This also works with adaptive clusters and launches and kill workers based on load.
        >>> cluster.adapt(maximum_jobs=20)
        """
        if security:
            self.security = security
        job_kwargs = self._modify_job_kwargs(
            job_kwargs,
            security=security,
            worker_image=worker_image,
            scheduler_port=scheduler_port,
            dashboard_port=dashboard_port,
            #nanny_port=nanny_port,
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
                           #nanny_port=DEFAULT_NANNY_PORT
                           ):
        job_config = job_kwargs.copy()
        input_files = []
        if CEPH_CONF.is_file() and KEYRING_CONF.is_file():
            input_files += [CEPH_CONF, KEYRING_CONF]
        if PIP_REQUIREMENTS.is_file():
            input_files += [PIP_REQUIREMENTS]
        if CONDA_ENV.is_file():
            input_files += [CONDA_ENV]
        # If we have certs in env, lets try to use TLS
        if (CA_FILE.is_file() and CERT_FILE.is_file() and cls.security().get_connection_args("scheduler")["require_encryption"]):
            job_config["protocol"] = "tls://"
            job_config["security"] = cls.security()
            input_files += [CA_FILE, CERT_FILE, XCACHE_FILE]
        else:
            raise KeyError("Please check with system administarator why you do not have a certificate.")
        files = ", ".join(str(path) for path in input_files)
        ## Networking settings
        try:
            external_ip = os.environ["HOST_IP"]
        except KeyError:
            print(
                "Please check with system administarator why external IP was not assigned for you."
            )
            sys.exit(1)
        scheduler_protocol = job_config["protocol"]
        if external_ip:
            address_list = [external_ip, DEFAULT_SCHEDULER_PORT]
            external_address_short = ":".join(str(item) for item in address_list)
            full_address_list = [scheduler_protocol, external_address_short]
            external_address = "".join(str(item) for item in full_address_list)
            external_ip_string = '"' + external_address + '"'
        # HTCondor logging
        job_config["log_directory"] = "logs"
        job_config["silence_logs"] = "DEBUG"
        ## Scheduler settings
        # we need to pass and check protocol for scheduler
        # (format should be not 'tls://'' but 'tls')
        job_config["scheduler_options"] = merge_dicts(
            {
                "port": scheduler_port,
                "dashboard_address": str(dashboard_port),
                "protocol": scheduler_protocol.replace("://", ""),
                "external_address": external_address,
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
                "docker_image": worker_image or dask.config.get(f"jobqueue.{cls.config_name}.worker-image")
            },
            {
                #"container_service_names": "dask,nanny",
                #"dask_container_port": DEFAULT_CONTAINER_PORT,
                #"nanny_container_port": nanny_port,
                "container_service_names": "dask",
                "dask_container_port": DEFAULT_CONTAINER_PORT,
            },
            {"transfer_input_files": files},
            {"encrypt_input_files": files},
            {"transfer_output_files": ""},
            {"when_to_transfer_output": "ON_EXIT"},
            {"should_transfer_files": "YES"},
            {"Stream_Output": "False"},
            {"Stream_Error": "False"},
            {"+DaskSchedulerAddress": external_ip_string},
            job_kwargs.get(
                "job_extra", dask.config.get(f"jobqueue.{cls.config_name}.job-extra")
            ),
        )
        print(job_config)
        return job_config

    @classmethod
    def security(cls):
        """
        Return the Dask ``Security`` object used by CoffeaCasa.
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
