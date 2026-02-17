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

HOME_DIR = Path.home()
PIP_REQUIREMENTS = HOME_DIR / "requirements.txt"
CONDA_ENV = HOME_DIR / "environment.yaml" if (HOME_DIR / "environment.yaml").is_file() else HOME_DIR / "environment.yml"

# Sentinel to cache the "no TLS" decision in the security property,
# distinguishing "not yet evaluated" (None) from "evaluated: no TLS" (_NO_SECURITY).
_NO_SECURITY = object()


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
                 **job_kwargs):

        # Assign cert paths
        self.ca_file = Path(ca_file) if ca_file else CA_FILE
        self.cert_file = Path(cert_file) if cert_file else CERT_FILE

        self._force_tcp = force_tcp
        self._security = security

        # FIX 1: Sanitize dask.config before the scheduler reads it.
        # The Labextension can inject dashboard_address=True (a boolean) into
        # dask config, which causes format_dashboard_link() to crash with:
        #   AttributeError: 'bool' object has no attribute 'format'
        raw_dashboard_link = dask.config.get("distributed.dashboard.link", None)
        if isinstance(raw_dashboard_link, bool):
            dask.config.set({"distributed.dashboard.link": "http://{host}:{port}/status"})

        # Check ports by attempting to bind rather than connect.
        # connect_ex("0.0.0.0", port) is unreliable — it checks reachability,
        # not whether something is already listening. A bind attempt is the
        # correct way to detect a port conflict. SO_REUSEADDR is set so that
        # recently-closed sockets in TIME_WAIT don't trigger false positives
        # between back-to-back test runs.
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
            scheduler_port=scheduler_port,
            dashboard_port=dashboard_port,
            nanny_port=nanny_port,
        )

        self._coffeacasa_scheduler_options = scheduler_opts

        super().__init__(
            scheduler_options=scheduler_opts,
            **job_kwargs,
        )

    # -----------------------------
    # Security property
    # -----------------------------
    @property
    def security(self):
        # FIX 3: Use _NO_SECURITY sentinel to cache the "no TLS" decision.
        # Previously, setting self._security = None in the no-TLS branch meant
        # every subsequent call re-entered the branch and re-checked the cert
        # files on disk. Now we distinguish:
        #   None        → not yet evaluated
        #   _NO_SECURITY → evaluated, no TLS available
        #   Security()  → evaluated, TLS enabled
        if self._security is _NO_SECURITY:
            return None
        if self._security is None:
            if self._force_tcp or not (self.ca_file.is_file() and self.cert_file.is_file()):
                self._security = _NO_SECURITY
                return None
            else:
                self._security = Security(
                    tls_ca_file=str(self.ca_file),
                    tls_worker_cert=str(self.cert_file),
                    tls_worker_key=str(self.cert_file),
                    tls_client_cert=str(self.cert_file),
                    tls_client_key=str(self.cert_file),
                    tls_scheduler_cert=str(self.cert_file),
                    tls_scheduler_key=str(self.cert_file),
                    require_encryption=True,
                )
        return self._security

    @security.setter
    def security(self, value):
        self._security = value

    # -----------------------------
    # Collect input files
    # -----------------------------
    def _collect_input_files(self):
        files = []

        # Environment files
        for f in [PIP_REQUIREMENTS, CONDA_ENV]:
            if f.is_file():
                files.append(f)

        # TLS certs
        sec = self.security
        if sec and self.ca_file.is_file() and self.cert_file.is_file() and sec.get_connection_args("scheduler")["require_encryption"]:
            files += [self.ca_file, self.cert_file]

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
        scheduler_port,
        dashboard_port,
    ):
        # Determine externally reachable IP
        external_ip = (
            os.environ.get("POD_IP")
            or os.environ.get("HOST_IP")
            or socket.getfqdn()
        )

        # Determine protocol
        sec = self.security
        use_tls = (
            sec is not None
            and sec.get_connection_args("scheduler").get("require_encryption", False)
        )

        protocol = "tls" if use_tls else "tcp"
        contact_address = f"{protocol}://{external_ip}:{scheduler_port}"

        # Default dashboard address
        default_dashboard_address = f":{dashboard_port}" if dashboard_port else None

        # Extract user scheduler options (e.g. from Labextension)
        user_opts = job_kwargs.get("scheduler_options", {}).copy()

        # Sanitize dashboard_address in user_opts: the Labextension may send
        # "dashboard_address": true (a boolean), which breaks the scheduler.
        if "dashboard_address" in user_opts:
            val = user_opts["dashboard_address"]
            if isinstance(val, bool):
                user_opts["dashboard_address"] = default_dashboard_address if val else None
            elif not isinstance(val, (str, type(None))):
                user_opts["dashboard_address"] = default_dashboard_address

        # Merge defaults with sanitized user options (user_opts wins).
        # NOTE: nanny_port is intentionally excluded here — Dask's Server.__init__()
        # does not accept it as a scheduler option. It is handled via the HTCondor
        # job directives (nanny_container_port) in _prepare_job_extra_directives.
        scheduler_opts = merge_dicts(
            {
                "port": scheduler_port,
                "dashboard_address": default_dashboard_address,
                "protocol": protocol,
                "contact_address": contact_address,
            },
            user_opts,
        )

        # FIX 1 (second layer): Hard post-merge guard.
        # Even if user_opts slips through with a non-string dashboard_address,
        # this ensures the scheduler always receives a str or None.
        if not isinstance(scheduler_opts.get("dashboard_address"), (str, type(None))):
            scheduler_opts["dashboard_address"] = default_dashboard_address

        return scheduler_opts

    # -----------------------------
    # Job extra directives
    # -----------------------------
    def _prepare_job_extra_directives(self, job_kwargs, worker_image, input_files, scheduler_options):
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

        # FIX 2: Use safe .get() with fallback instead of os.environ["HOST_IP"],
        # which raises a hard KeyError if the variable is not set.
        # This is consistent with the fallback chain in _prepare_scheduler_options.
        external_ip = (
            os.environ.get("HOST_IP")
            or os.environ.get("POD_IP")
            or socket.getfqdn()
        )

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
                "encrypt_input_files": files_str,
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
    def _modify_job_kwargs(self, job_kwargs, *, worker_image=None, scheduler_port=DEFAULT_SCHEDULER_PORT, dashboard_port=DEFAULT_DASHBOARD_PORT, nanny_port=DEFAULT_NANNY_PORT):
        job_config = job_kwargs.copy()

        # Input files
        input_files = self._collect_input_files()

        # Scheduler options — nanny_port is handled in job directives, not here
        scheduler_opts = self._prepare_scheduler_options(
            job_config, scheduler_port, dashboard_port
        )

        # Job extra directives
        job_config["job_extra_directives"] = self._prepare_job_extra_directives(
            job_config, worker_image, input_files, scheduler_opts
        )

        # Remove cluster-level keys
        for k in ["scheduler_port", "dashboard_port", "security"]:
            job_config.pop(k, None)

        return job_config, scheduler_opts
