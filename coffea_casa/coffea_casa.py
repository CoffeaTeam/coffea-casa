"""CoffeaCasaCluster class
"""
import os
from pathlib import Path
import sys
import dask
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob
from distributed.security import Security

# Port settings
DEFAULT_SCHEDULER_PORT = 8786
DEFAULT_DASHBOARD_PORT = 8787
DEFAULT_CONTAINER_PORT = 8786
DEFAULT_NANNY_PORT = 8001

# Security settings for Dask scheduler
# REMOVE ME (backward compatibity for now)
SECRETS_DIR = Path("/etc/cmsaf-secrets")
SECRETS_DIR_CHOWN = Path("/etc/cmsaf-secrets-chown")
CA_FILE = SECRETS_DIR / "ca.pem"
CERT_FILE = SECRETS_DIR / "hostcert.pem"
HOME_DIR = Path.home()
# XCache
#XCACHE_SCITOKEN_FILE = SECRETS_DIR_CHOWN / "access_token"
# pip
PIP_REQUIREMENTS = HOME_DIR / "requirements.txt"
# conda, with yml/yaml both supported
if (HOME_DIR / "environment.yaml").is_file():
    CONDA_ENV = HOME_DIR / "environment.yaml"
else:
    CONDA_ENV = HOME_DIR / "environment.yml"

import os
from pathlib import Path

def bearer_token_path():
    """Return the path to the user's X.509 proxy or None if not found"""

    def check_token_path(path, suffix=''):
        token_path = f'{path}{suffix}'
        if Path(token_path).is_file():
            return token_path
        return None

    # 1. Check BEARER_TOKEN_FILE env variable
    try:
        path = check_token_path(os.environ['BEARER_TOKEN_FILE'])
        if path:
            return path
    except KeyError:
        pass

    # 2. Check XDG_RUNTIME_DIR + /bt_u$UID
    try:
        xdg_runtime_dir = os.environ['XDG_RUNTIME_DIR']
        path = check_token_path(xdg_runtime_dir, suffix=f'/bt_u{os.geteuid()}')
        if path:
            return path
    except KeyError:
        pass

    # 3. Check /tmp/bt_u$UID
    try:
        path = check_token_path(f'/tmp/bt_u{os.geteuid()}')
        if path:
            return path
    except KeyError:
        pass

    return None

def x509_user_proxy_path():
    """Return the path to the user's X.509 proxy or raise FileNotFoundError if it doesn't exist on disk
    """
    try:
        path = os.environ['X509_USER_PROXY']
    except KeyError:
        path = f'/tmp/x509up_u{os.geteuid()}'

    if open(path):
        return path
    return None  # we shouldn't get here; failure to open should raise OSError

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
                 nanny_port=DEFAULT_NANNY_PORT,
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
        job_extra_directives : dict
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
            nanny_port=nanny_port,
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
                           nanny_port=DEFAULT_NANNY_PORT
                           ):
        job_config = job_kwargs.copy()
        input_files = []
        if PIP_REQUIREMENTS.is_file():
            input_files += [PIP_REQUIREMENTS]
        if CONDA_ENV.is_file():
            input_files += [CONDA_ENV]
        opendata = os.environ.get('OPENDATA_INSTANCE')
        # If we have certs in env, lets try to use TLS
        if (CA_FILE.is_file() and CERT_FILE.is_file() and cls.security().get_connection_args("scheduler")["require_encryption"]):
            job_config["protocol"] = "tls://"
            job_config["security"] = cls.security()
            input_files += [CA_FILE, CERT_FILE]
        XCACHE_SCITOKEN_FILE = bearer_token_path()
        if XCACHE_SCITOKEN_FILE:
            input_files += [XCACHE_SCITOKEN_FILE]
        else:
            print("Warning: No bearer token found — proceeding without it.")
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
            contact_address = "".join(str(item) for item in full_address_list)
            external_ip_string = '"' + contact_address + '"'
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
                "contact_address": contact_address,
            },
            job_kwargs.get(
                "scheduler_options",
                dask.config.get(f"jobqueue.{cls.config_name}.scheduler-options"),
            ),
        )
        # try in case we have x509 proxy
        try:
            proxy = x509_user_proxy_path()
            if proxy:
                use_proxy = True
        except:
            use_proxy = False
            pass
        ## Job extra settings (HTCondor ClassAd)
        job_config["job_extra_directives"] = merge_dicts(
            {
                "universe": "docker",
                "docker_image": worker_image or dask.config.get(f"jobqueue.{cls.config_name}.worker-image")
            },
            {
                "container_service_names": "dask,nanny",
                "dask_container_port": DEFAULT_CONTAINER_PORT,
                "nanny_container_port": DEFAULT_NANNY_PORT,
            },
            {"use_x509userproxy": use_proxy},
            {"transfer_input_files": files},
            {"encrypt_input_files": files},
            {"transfer_output_files": ""},
            {"when_to_transfer_output": "ON_EXIT"},
            {"should_transfer_files": "YES"},
            {"Stream_Output": "False"},
            {"Stream_Error": "False"},
            {"+CoffeaCasaWorkerType": '"dask"'},
            {"+DaskSchedulerAddress": external_ip_string},
            {"+AccountingGroup": '"cms.other.coffea.$ENV(HOSTNAME)"'},
            job_kwargs.get(
                "job_extra_directives", dask.config.get(f"jobqueue.{cls.config_name}.job_extra_directives")
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
