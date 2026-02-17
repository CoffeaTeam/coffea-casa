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
KEY_FILE = SECRETS_DIR / "hostkey.pem"   # private key — may be separate from cert

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
                 **job_kwargs):

        # Assign cert paths.
        # key_file defaults to hostkey.pem if it exists, otherwise falls back
        # to cert_file (for combined cert+key PEM bundles).
        self.ca_file = Path(ca_file) if ca_file else CA_FILE
        self.cert_file = Path(cert_file) if cert_file else CERT_FILE
        _key_default = KEY_FILE if KEY_FILE.is_file() else self.cert_file
        self.key_file = Path(key_file) if key_file else _key_default
        self._force_tcp = force_tcp

        # Sanitize dask.config before the scheduler reads it.
        # The Labextension can inject dashboard_address=True (a boolean) into
        # dask config, which causes format_dashboard_link() to crash with:
        #   AttributeError: 'bool' object has no attribute 'format'
        raw_dashboard_link = dask.config.get("distributed.dashboard.link", None)
        if isinstance(raw_dashboard_link, bool):
            dask.config.set({"distributed.dashboard.link": "http://{host}:{port}/status"})

        # Resolve security before sanitizing dask.config so we know the
        # actual encryption state. We do this early (before _modify_job_kwargs)
        # because _prepare_scheduler_options also reads resolved_security.
        resolved_security = self._resolve_security(security)

        # Align dask.config with our resolved security state.
        #
        # Problem 1: dask.yaml (mounted as a k8s ConfigMap) has
        #   distributed.comm.require-encryption: true
        # SpecCluster reads this independently of the security= kwarg, so even
        # with security=None it refuses tcp:// with:
        #   RuntimeError: encryption required by Dask configuration,
        #   refusing communication from/to 'tcp://:8786'
        #
        # Problem 2: dask.yaml may have worker TLS cert/key set to null:
        #   distributed.comm.tls.worker.cert: null
        #   distributed.comm.tls.worker.key: null
        # This causes ssl_context=None at worker bind time even though the
        # scheduler and client sections are correctly populated. The worker
        # reads this config independently of the --tls-cert CLI flag when
        # building its listening socket.
        #
        # We patch both issues here so the config always matches reality.
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

        # Check ports by attempting to bind rather than connect.
        # connect_ex("0.0.0.0", port) checks reachability, not availability.
        # A bind attempt is the correct way to detect a port conflict.
        # SO_REUSEADDR prevents TIME_WAIT false positives in back-to-back tests.
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
            # security=None: do not let dask-jobqueue inject --tls-* flags into
            # the worker Arguments — the startup script handles TLS correctly.
            security=None,
            scheduler_options=scheduler_opts,
            **job_kwargs,
        )

    # -----------------------------
    # Security resolution
    # -----------------------------
    def _resolve_security(self, security) -> Security | None:
        """
        Resolve and validate the Security object for this cluster.

        If security is explicitly passed in, use it as-is.
        Otherwise, attempt to build a TLS Security from the cert files,
        probing ssl.SSLContext to ensure they are actually loadable.
        Falls back to None (TCP) with a warning if loading fails.
        """
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

        # Probe: verify ssl.SSLContext can actually load the certs.
        # Security() constructor always succeeds even with unloadable certs --
        # the ssl_context=None crash only surfaces later at worker bind time.
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_verify_locations(cafile=str(self.ca_file))
            ctx.load_cert_chain(
                certfile=str(self.cert_file),
                keyfile=str(self.key_file),
            )
        except ssl.SSLError as e:
            logger.warning(
                "CoffeaCasaCluster: TLS cert files exist but ssl.SSLContext "
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

    # -----------------------------
    # Collect input files
    # -----------------------------
    def _collect_input_files(self, resolved_security):
        files = []

        # Environment files
        for f in [PIP_REQUIREMENTS, CONDA_ENV]:
            if f.is_file():
                files.append(f)

        # TLS certs — transfer into worker container so startup script can use them
        if (
            resolved_security is not None
            and self.ca_file.is_file()
            and self.cert_file.is_file()
            and resolved_security.get_connection_args("scheduler").get("require_encryption", False)
        ):
            files += [self.ca_file, self.cert_file]
            # Also transfer key file if it's separate from the cert
            if self.key_file != self.cert_file and self.key_file.is_file():
                files.append(self.key_file)

        # XCache bearer token
        token_path = bearer_token_path()
        if token_path:
            files.append(token_path)

        return files

    # -----------------------------
    # Scheduler options
    # -----------------------------
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
        # Determine externally reachable IP
        external_ip = (
            os.environ.get("POD_IP")
            or os.environ.get("HOST_IP")
            or socket.getfqdn()
        )

        # Determine protocol from the already-resolved security object
        use_tls = (
            resolved_security is not None
            and resolved_security.get_connection_args("scheduler").get("require_encryption", False)
        )

        protocol = "tls" if use_tls else "tcp"
        contact_address = f"{protocol}://{external_ip}:{scheduler_port}"

        # Default dashboard address
        default_dashboard_address = f":{dashboard_port}" if dashboard_port else None

        # Extract user scheduler options (e.g. from Labextension)
        user_opts = job_kwargs.get("scheduler_options", {}).copy()

        # Sanitize dashboard_address: the Labextension may send True (a boolean)
        if "dashboard_address" in user_opts:
            val = user_opts["dashboard_address"]
            if isinstance(val, bool):
                user_opts["dashboard_address"] = default_dashboard_address if val else None
            elif not isinstance(val, (str, type(None))):
                user_opts["dashboard_address"] = default_dashboard_address

        # nanny_port intentionally excluded — Dask's Server.__init__() does not
        # accept it. It is handled via HTCondor job directives instead.
        scheduler_opts = merge_dicts(
            {
                "port": scheduler_port,
                "dashboard_address": default_dashboard_address,
                "protocol": protocol,
                "contact_address": contact_address,
            },
            user_opts,
        )

        # Hard post-merge guard: ensure dashboard_address is always str or None
        if not isinstance(scheduler_opts.get("dashboard_address"), (str, type(None))):
            scheduler_opts["dashboard_address"] = default_dashboard_address

        return scheduler_opts

    # -----------------------------
    # Job extra directives
    # -----------------------------
    def _prepare_job_extra_directives(self, job_kwargs, worker_image, input_files, scheduler_options, resolved_security):
        # Determine if X.509 proxy exists
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

        return merge_dicts(
            {
                "universe": "docker",
                "docker_image": worker_image or dask.config.get(f"jobqueue.{self.config_name}.worker-image"),
                "container_service_names": "dask,nanny",
                "dask_container_port": DEFAULT_CONTAINER_PORT,
                "nanny_container_port": DEFAULT_NANNY_PORT,
                "use_x509userproxy": use_proxy,
                "transfer_input_files": files_str,
                # Note: encrypt_input_files removed — HTCondor encryption requires
                # matching daemon keys and can cause silent cert corruption.
                # Certs are already protected by TLS in transit.
                "transfer_output_files": "",
                "when_to_transfer_output": "ON_EXIT",
                "should_transfer_files": "YES",
                "Stream_Output": "False",
                "Stream_Error": "False",
                "+CoffeaCasaWorkerType": '"dask"',
                "+DaskSchedulerAddress": f'"{contact_address}"',
                "+AccountingGroup": '"cms.other.coffea.$ENV(HOSTNAME)"',
            },
            job_kwargs.get("job_extra_directives", {}),
        )

    # -----------------------------
    # Orchestrate job kwargs
    # -----------------------------
    def _modify_job_kwargs(self, job_kwargs, *, worker_image=None, resolved_security=None, scheduler_port=DEFAULT_SCHEDULER_PORT, dashboard_port=DEFAULT_DASHBOARD_PORT, nanny_port=DEFAULT_NANNY_PORT):
        job_config = job_kwargs.copy()

        # Input files
        input_files = self._collect_input_files(resolved_security)

        # Scheduler options
        scheduler_opts = self._prepare_scheduler_options(
            job_config, resolved_security, scheduler_port, dashboard_port
        )

        # Job extra directives
        job_config["job_extra_directives"] = self._prepare_job_extra_directives(
            job_config, worker_image, input_files, scheduler_opts, resolved_security
        )

        # Remove cluster-level keys that don't belong in job kwargs
        for k in ["scheduler_port", "dashboard_port", "security"]:
            job_config.pop(k, None)

        return job_config, scheduler_opts
