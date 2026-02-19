"""CoffeaCasaCluster class"""
import os
from pathlib import Path
import sys
import socket
import dask
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob
from distributed.security import Security

# Port settings
DEFAULT_SCHEDULER_PORT = 8786
DEFAULT_DASHBOARD_PORT = 8785
DEFAULT_CONTAINER_PORT = 8786
DEFAULT_NANNY_PORT = 8001

# Security settings for Dask scheduler
SECRETS_DIR = Path("/etc/cmsaf-secrets")
SECRETS_DIR_CHOWN = Path("/etc/cmsaf-secrets-chown")
CA_FILE = SECRETS_DIR / "ca.pem"
CERT_FILE = SECRETS_DIR / "hostcert.pem"
KEY_FILE = SECRETS_DIR / "hostkey.pem"
HOME_DIR = Path.home()
PIP_REQUIREMENTS = HOME_DIR / "requirements.txt"

# conda, with yml/yaml both supported
if (HOME_DIR / "environment.yaml").is_file():
    CONDA_ENV = HOME_DIR / "environment.yaml"
else:
    CONDA_ENV = HOME_DIR / "environment.yml"


def bearer_token_path():
    """Return the path to the bearer token or None if not found"""
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

    # 2. Check /etc/cmsaf-secrets-chown/access_token (CMS AF mounted token)
    path = check_token_path('/etc/cmsaf-secrets-chown/access_token')
    if path:
        return path

    # 3. Check XDG_RUNTIME_DIR + /bt_u$UID
    try:
        xdg_runtime_dir = os.environ['XDG_RUNTIME_DIR']
        path = check_token_path(xdg_runtime_dir, suffix=f'/bt_u{os.geteuid()}')
        if path:
            return path
    except KeyError:
        pass

    # 4. Check /tmp/bt_u$UID
    path = check_token_path(f'/tmp/bt_u{os.geteuid()}')
    if path:
        return path

    return None


def x509_user_proxy_path():
    """Return the path to the user's X.509 proxy or None if not found"""
    try:
        path = os.environ['X509_USER_PROXY']
    except KeyError:
        path = f'/tmp/x509up_u{os.geteuid()}'

    if Path(path).is_file():
        return path
    return None


def merge_dicts(*dict_args):
    """Merge dictionaries, precedence goes to latter dictionaries"""
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


class CoffeaCasaJob(HTCondorJob):
    submit_command = "condor_submit -spool"
    config_name = "coffea-casa"


class CoffeaCasaCluster(HTCondorCluster):
    """
    Subclass for launching Dask via HTCondor in CMS facilities.
    """
    job_cls = CoffeaCasaJob
    config_name = "coffea-casa"

    def __init__(self,
                 *,
                 security=None,
                 force_tcp=False,
                 worker_image=None,
                 scheduler_options=None,
                 scheduler_port=DEFAULT_SCHEDULER_PORT,
                 dashboard_port=DEFAULT_DASHBOARD_PORT,
                 nanny_port=DEFAULT_NANNY_PORT,
                 check_ports=False,
                 **job_kwargs):
        """
        Parameters
        ----------
        security : distributed.Security, optional
            Security object for TLS configuration
        force_tcp : bool, default False
            Force TCP instead of TLS
        worker_image : str, optional
            Docker image for workers
        scheduler_port : int, default 8786
            Scheduler port
        dashboard_port : int, default 8785
            Dashboard port
        nanny_port : int, default 8001
            Nanny port
        check_ports : bool, default False
            Check if ports are available before starting
        **job_kwargs
            Additional job configuration
        """
        self._force_tcp = force_tcp

        raw_dashboard_link = dask.config.get("distributed.dashboard.link", None)
        if isinstance(raw_dashboard_link, bool):
            dask.config.set({"distributed.dashboard.link": "http://{host}:{port}/status"})

        if not force_tcp:
            worker_cert = dask.config.get("distributed.comm.tls.worker.cert", None)
            worker_key = dask.config.get("distributed.comm.tls.worker.key", None)
            if not worker_cert or not worker_key:
                dask.config.set({
                    "distributed.comm.tls.worker.cert": str(CERT_FILE),
                    "distributed.comm.tls.worker.key": str(KEY_FILE if KEY_FILE.is_file() else CERT_FILE),
                })

        will_use_tls = (
            not force_tcp 
            and CA_FILE.is_file() 
            and CERT_FILE.is_file()
            and security_obj().get_connection_args("scheduler").get("require_encryption", False)
        )
        dask.config.set({"distributed.comm.require-encryption": will_use_tls})

        # FIX 4: Optional port conflict check (disabled by default)
        if check_ports:
            for port in (scheduler_port, dashboard_port, nanny_port):
                if port:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        try:
                            s.bind(("0.0.0.0", port))
                        except OSError:
                            raise RuntimeError(f"Port {port} already in use.")

        if security:
            self.security = security

        job_kwargs = self._modify_job_kwargs(
            job_kwargs,
            security=security,
            force_tcp=force_tcp,
            worker_image=worker_image,
            scheduler_port=scheduler_port,
            dashboard_port=dashboard_port,
            nanny_port=nanny_port,
        )

        super().__init__(**job_kwargs)

    @classmethod
    def _modify_job_kwargs(cls,
                           job_kwargs,
                           *,
                           security=None,
                           force_tcp=False,
                           worker_image=None,
                           scheduler_options=None,
                           scheduler_port=DEFAULT_SCHEDULER_PORT,
                           dashboard_port=DEFAULT_DASHBOARD_PORT,
                           nanny_port=DEFAULT_NANNY_PORT):
        job_config = job_kwargs.copy()
        input_files = []

        if PIP_REQUIREMENTS.is_file():
            input_files.append(PIP_REQUIREMENTS)
        if CONDA_ENV.is_file():
            input_files.append(CONDA_ENV)

        # If we have certs and not forcing TCP, use TLS
        if (not force_tcp 
            and CA_FILE.is_file() 
            and CERT_FILE.is_file() 
            and security_obj().get_connection_args("scheduler")["require_encryption"]):
            job_config["protocol"] = "tls://"
            job_config["security"] = security_obj()
            input_files += [CA_FILE, CERT_FILE]
            # Add separate key file if it exists
            if KEY_FILE.is_file() and KEY_FILE != CERT_FILE:
                input_files.append(KEY_FILE)
        else:
            job_config["protocol"] = "tcp://"

        # Add bearer token if found
        token_file = bearer_token_path()
        if token_file:
            input_files.append(token_file)

        files = ", ".join(str(path) for path in input_files)

        # Networking settings
        try:
            external_ip = os.environ.get("POD_IP") or os.environ.get("HOST_IP") or socket.getfqdn()
        except Exception:
            print("Warning: Could not determine external IP")
            external_ip = "127.0.0.1"

        scheduler_protocol = job_config["protocol"]
        address_list = [external_ip, str(scheduler_port)]
        external_address_short = ":".join(address_list)
        full_address_list = [scheduler_protocol, external_address_short]
        contact_address = "".join(full_address_list)
        external_ip_string = f'"{contact_address}"'

        dash_port = f":{dashboard_port}"

        # Scheduler settings
        job_config["scheduler_options"] = merge_dicts(
            {
                "port": scheduler_port,
                "dashboard_address": dash_port,
                "protocol": scheduler_protocol.replace("://", ""),
                "contact_address": contact_address,
            },
            job_kwargs.get("scheduler_options", 
                         dask.config.get(f"jobqueue.{cls.config_name}.scheduler-options", {})),
        )

        # Check for x509 proxy
        proxy = x509_user_proxy_path()
        use_proxy = proxy is not None

        # Job extra settings (HTCondor ClassAd)
        job_config["job_extra_directives"] = merge_dicts(
            {
                "universe": "docker",
                "docker_image": worker_image or dask.config.get(f"jobqueue.{cls.config_name}.worker-image"),
                "container_service_names": "dask,nanny",
                "dask_container_port": DEFAULT_CONTAINER_PORT,
                "nanny_container_port": DEFAULT_NANNY_PORT,
                "use_x509userproxy": use_proxy,
                "transfer_input_files": files,
                "encrypt_input_files": files,
                "transfer_output_files": "",
                "when_to_transfer_output": "ON_EXIT",
                "should_transfer_files": "YES",
                "+CoffeaCasaWorkerType": '"dask"',
                "+DaskSchedulerAddress": external_ip_string,
                "+AccountingGroup": '"cms.other.coffea.$ENV(HOSTNAME)"',
            },
            job_kwargs.get("job_extra_directives",
                         dask.config.get(f"jobqueue.{cls.config_name}.job_extra_directives", {})),
        )

        return job_config


def security_obj():
    """Return the Dask Security object used by CoffeaCasa"""
    ca_file = str(CA_FILE)
    cert_file = str(CERT_FILE)
    key_file = str(KEY_FILE if KEY_FILE.is_file() else CERT_FILE)
    
    return Security(
        tls_ca_file=ca_file,
        tls_worker_cert=cert_file,
        tls_worker_key=key_file,
        tls_client_cert=cert_file,
        tls_client_key=key_file,
        tls_scheduler_cert=cert_file,
        tls_scheduler_key=key_file,
        require_encryption=True,
    )