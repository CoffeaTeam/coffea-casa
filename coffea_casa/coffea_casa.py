"""CoffeaCasaCluster class"""
import os
from pathlib import Path
import socket
import dask
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob
from distributed.security import Security

# Default ports
DEFAULT_SCHEDULER_PORT = 8786
DEFAULT_DASHBOARD_PORT = 8785
DEFAULT_NANNY_PORT = 8001
DEFAULT_CONTAINER_PORT = 8786

# Default cert paths
SECRETS_DIR = Path("/etc/cmsaf-secrets")
CA_FILE = SECRETS_DIR / "ca.pem"
CERT_FILE = SECRETS_DIR / "hostcert.pem"
KEY_FILE = SECRETS_DIR / "hostkey.pem"

HOME_DIR = Path.home()
PIP_REQUIREMENTS = HOME_DIR / "requirements.txt"
CONDA_ENV = (
    HOME_DIR / "environment.yaml"
    if (HOME_DIR / "environment.yaml").is_file()
    else HOME_DIR / "environment.yml"
)


def bearer_token_path() -> Path | None:
    """Return path to user's XCache bearer token if it exists"""
    uid = os.geteuid()
    candidates = [
        os.environ.get("BEARER_TOKEN_FILE"),
        "/etc/cmsaf-secrets-chown/access_token",  # CMS AF mounted token
        os.path.join(os.environ.get("XDG_RUNTIME_DIR", ""), f"bt_u{uid}"),
        f"/tmp/bt_u{uid}",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return Path(path)
    return None


def x509_user_proxy_path() -> Path:
    """Return path to user's X.509 proxy, raise if missing"""
    path = Path(os.environ.get("X509_USER_PROXY", f"/tmp/x509up_u{os.geteuid()}"))
    if path.is_file():
        return path
    raise FileNotFoundError(f"X.509 proxy not found at {path}")


def merge_dicts(*dicts):
    """Shallow merge dictionaries (latter dicts override earlier ones)"""
    result = {}
    for d in dicts:
        result.update(d)
    return result


class CoffeaCasaJob(HTCondorJob):
    submit_command = "condor_submit -spool"
    config_name = "coffea-casa"


class CoffeaCasaCluster(HTCondorCluster):
    job_cls = CoffeaCasaJob
    config_name = "coffea-casa"

    def __init__(self,
                 *,
                 worker_image=None,
                 security=None,
                 force_tcp: bool = False,
                 scheduler_port=DEFAULT_SCHEDULER_PORT,
                 dashboard_port=DEFAULT_DASHBOARD_PORT,
                 nanny_port=DEFAULT_NANNY_PORT,
                 ca_file=None,
                 cert_file=None,
                 key_file=None,
                 check_ports=False,
                 **job_kwargs):

        # Assign cert paths
        self.ca_file = Path(ca_file) if ca_file else CA_FILE
        self.cert_file = Path(cert_file) if cert_file else CERT_FILE
        _key_default = KEY_FILE if KEY_FILE.is_file() else self.cert_file
        self.key_file = Path(key_file) if key_file else _key_default
        self._force_tcp = force_tcp

        # Sanitize dask.config before scheduler reads it
        raw_dashboard_link = dask.config.get("distributed.dashboard.link", None)
        if isinstance(raw_dashboard_link, bool):
            dask.config.set({"distributed.dashboard.link": "http://{host}:{port}/status"})

        # Resolve security early
        resolved_security = self._resolve_security(security)

        # Align dask.config with resolved security state
        if resolved_security is not None:
            worker_cert = dask.config.get("distributed.comm.tls.worker.cert", None)
            worker_key = dask.config.get("distributed.comm.tls.worker.key", None)
            if not worker_cert or not worker_key:
                dask.config.set({
                    "distributed.comm.tls.worker.cert": str(self.cert_file),
                    "distributed.comm.tls.worker.key": str(self.key_file),
                })
        dask.config.set({
            "distributed.comm.require-encryption": resolved_security is not None
        })

        # Optional port conflict check (disabled by default to avoid blocking Labextension)
        # The scheduler will fail with a clear error if ports are in use anyway
        if check_ports:
            for port in (scheduler_port, dashboard_port, nanny_port):
                if port:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        try:
                            s.bind(("0.0.0.0", port))
                        except OSError:
                            raise RuntimeError(f"Port {port} already in use.")

        # Prepare job kwargs and scheduler options
        job_kwargs, scheduler_opts = self._modify_job_kwargs(
            job_kwargs,
            worker_image=worker_image,
            resolved_security=resolved_security,
            scheduler_port=scheduler_port,
            dashboard_port=dashboard_port,
            nanny_port=nanny_port,
        )

        self._coffeacasa_scheduler_options = scheduler_opts

        super().__init__(
            # Pass security=None so dask-jobqueue doesn't inject --tls-* flags
            # with scheduler-side paths (/etc/cmsaf-secrets/ca.pem).
            # We set TLS config via environment variables pointing to
            # $_CONDOR_SCRATCH_DIR where HTCondor drops transferred files.
            security=None,
            scheduler_options=scheduler_opts,
            **job_kwargs,
        )

    def _resolve_security(self, security) -> Security | None:
        """Resolve and validate Security object"""
        import logging
        import ssl
        logger = logging.getLogger(__name__)

        if security is not None:
            return security

        if self._force_tcp:
            logger.info("CoffeaCasaCluster: force_tcp=True, using unencrypted TCP")
            return None

        if not (self.ca_file.is_file() and self.cert_file.is_file()):
            logger.warning(
                "CoffeaCasaCluster: TLS cert files not found at %s and %s -- "
                "falling back to unencrypted TCP.",
                self.ca_file, self.cert_file,
            )
            return None

        # Verify ssl.SSLContext can load the certs
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_verify_locations(cafile=str(self.ca_file))
            ctx.load_cert_chain(
                certfile=str(self.cert_file),
                keyfile=str(self.key_file),
            )
        except ssl.SSLError as e:
            logger.warning(
                "CoffeaCasaCluster: TLS certs exist but ssl.SSLContext "
                "could not load them (%s) -- falling back to TCP. "
                "cert=%s key=%s",
                e, self.cert_file, self.key_file,
            )
            return None
        except Exception as e:
            logger.warning(
                "CoffeaCasaCluster: unexpected error loading TLS certs (%s) "
                "-- falling back to TCP.", e,
            )
            return None

        return Security(
            tls_ca_file=str(self.ca_file),
            tls_worker_cert=str(self.cert_file),
            tls_worker_key=str(self.key_file),
            tls_client_cert=str(self.cert_file),
            tls_client_key=str(self.key_file),
            tls_scheduler_cert=str(self.cert_file),
            tls_scheduler_key=str(self.key_file),
            require_encryption=True,
        )

    def _collect_input_files(self, resolved_security):
        """Collect files to transfer to worker container"""
        files = []

        # Environment files
        for f in [PIP_REQUIREMENTS, CONDA_ENV]:
            if f.is_file():
                files.append(f)

        # TLS certs - transferred via HTCondor to $_CONDOR_SCRATCH_DIR
        # (worker containers don't have /etc/cmsaf-secrets/ mounted)
        if (
            resolved_security is not None
            and self.ca_file.is_file()
            and self.cert_file.is_file()
            and resolved_security.get_connection_args("scheduler").get("require_encryption", False)
        ):
            files += [self.ca_file, self.cert_file]
            if self.key_file != self.cert_file and self.key_file.is_file():
                files.append(self.key_file)

        # XCache bearer token
        token_path = bearer_token_path()
        if token_path:
            files.append(token_path)

        return files

    @property
    def coffeacasa_scheduler_options(self):
        return getattr(self, "_coffeacasa_scheduler_options", {})

    def _prepare_scheduler_options(
        self,
        job_kwargs,
        resolved_security,
        scheduler_port,
        dashboard_port,
    ):
        """Prepare scheduler options dict"""
        external_ip = (
            os.environ.get("POD_IP")
            or os.environ.get("HOST_IP")
            or socket.getfqdn()
        )

        use_tls = (
            resolved_security is not None
            and resolved_security.get_connection_args("scheduler").get("require_encryption", False)
        )

        protocol = "tls" if use_tls else "tcp"
        contact_address = f"{protocol}://{external_ip}:{scheduler_port}"
        default_dashboard_address = f":{dashboard_port}" if dashboard_port else None

        user_opts = job_kwargs.get("scheduler_options", {}).copy()

        # Sanitize dashboard_address
        if "dashboard_address" in user_opts:
            val = user_opts["dashboard_address"]
            if isinstance(val, bool):
                user_opts["dashboard_address"] = default_dashboard_address if val else None
            elif not isinstance(val, (str, type(None))):
                user_opts["dashboard_address"] = default_dashboard_address

        scheduler_opts = merge_dicts(
            {
                "port": scheduler_port,
                "dashboard_address": default_dashboard_address,
                "protocol": protocol,
                "contact_address": contact_address,
            },
            user_opts,
        )

        # Post-merge guard
        if not isinstance(scheduler_opts.get("dashboard_address"), (str, type(None))):
            scheduler_opts["dashboard_address"] = default_dashboard_address

        return scheduler_opts

    def _prepare_job_extra_directives(self, job_kwargs, worker_image, input_files, scheduler_options, resolved_security):
        """Prepare HTCondor job directives"""
        # Check for X.509 proxy
        use_proxy = False
        proxy_env = os.environ.get("X509_USER_PROXY")
        if proxy_env and Path(proxy_env).is_file():
            use_proxy = True
        else:
            try:
                proxy_path = x509_user_proxy_path()
                use_proxy = proxy_path.is_file()
            except FileNotFoundError:
                use_proxy = False

        files_str = ", ".join(str(p) for p in input_files)
        contact_address = scheduler_options["contact_address"]

        directives = {
            "universe": "docker",
            "docker_image": worker_image or dask.config.get(f"jobqueue.{self.config_name}.worker-image"),
            "container_service_names": "dask,nanny",
            "dask_container_port": DEFAULT_CONTAINER_PORT,
            "nanny_container_port": DEFAULT_NANNY_PORT,
            "use_x509userproxy": use_proxy,
            "transfer_input_files": files_str,
            "encrypt_input_files": files_str,
            "output": "logs/worker-$(ClusterId).$(ProcId).out",
            "error": "logs/worker-$(ClusterId).$(ProcId).err",
            "log": "logs/worker-$(ClusterId).log",
            "when_to_transfer_output": "ON_EXIT_OR_EVICT",
            "should_transfer_files": "YES",
            "stream_output": True,
            "stream_error": True,
            "+CoffeaCasaWorkerType": '"dask"',
            "+DaskSchedulerAddress": f'"{contact_address}"',
            "+AccountingGroup": '"cms.other.coffea.$ENV(HOSTNAME)"',
        }

        return merge_dicts(directives, job_kwargs.get("job_extra_directives", {}))

    def _modify_job_kwargs(self, job_kwargs, *, worker_image=None, resolved_security=None, scheduler_port=DEFAULT_SCHEDULER_PORT, dashboard_port=DEFAULT_DASHBOARD_PORT, nanny_port=DEFAULT_NANNY_PORT):
        """Orchestrate job kwargs preparation"""
        job_config = job_kwargs.copy()

        input_files = self._collect_input_files(resolved_security)

        scheduler_opts = self._prepare_scheduler_options(
            job_config, resolved_security, scheduler_port, dashboard_port
        )

        job_config["job_extra_directives"] = self._prepare_job_extra_directives(
            job_config, worker_image, input_files, scheduler_opts, resolved_security
        )

        # Remove cluster-level keys
        for k in ["scheduler_port", "dashboard_port", "security"]:
            job_config.pop(k, None)

        return job_config, scheduler_opts