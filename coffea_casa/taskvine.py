"""TaskVine workers on HTCondor for a manager running in the notebook (#167).

A TaskVine manager (``ndcctools.taskvine.Manager``, or the one inside
``vine_reduce``'s ``TaskVineDistributor``) runs in the user's notebook and
listens on the port the facility routes to it (8786, the Dask scheduler
port). :class:`CoffeaCasaVineWorkers` submits HTCondor jobs running the
facility worker image; its entrypoint starts ``vine_worker``, which connects
back to the manager over TLS.

Workers are submitted like :class:`~coffea_casa.CoffeaCasaCluster`'s Dask
workers: the bearer token is sent encrypted, site job settings from dask
config (``jobqueue.coffea-casa.job-extra-directives``, e.g. the accounting
group) apply, and the notebook's environment is *not* copied into the job.
"""
import re
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

import dask
from dask_jobqueue.htcondor import quote_environment

from .coffea_casa import (
    DEFAULT_LOG_DIR,
    DEFAULT_SCHEDULER_PORT,
    _keep_files_encrypted,
    bearer_token_path,
    external_host,
    fetch_spooled_logs,
    worker_passthrough_env,
    x509_user_proxy_path,
)

CONFIG_NAME = "coffea-casa"
# The per-user route to the notebook forwards only this port, so the manager
# shares it with CoffeaCasaCluster's scheduler: run one or the other.
DEFAULT_MANAGER_PORT = DEFAULT_SCHEDULER_PORT
# Port vine_worker listens on inside its container for worker-to-worker
# transfers; HTCondor forwards it (container service "vine").
VINE_CONTAINER_PORT = 9123


def _check_port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
        except OSError:
            raise RuntimeError(
                f"Port {port} is already in use. HTCondor workers can only reach "
                f"this notebook on port {port}, which a Dask cluster "
                "(CoffeaCasaCluster, or one started from the Dask sidebar) may be "
                "using: close it first.") from None


def vine_manager(port=DEFAULT_MANAGER_PORT, name=None, **kwargs):
    """Create a TaskVine manager that coffea-casa's HTCondor workers can reach.

    The manager listens on `port` (default 8786) with TLS, which
    :class:`CoffeaCasaVineWorkers` requires. Extra keyword arguments go to
    ``ndcctools.taskvine.Manager``. With vine_reduce, pass ``port=8786`` to
    ``TaskVineDistributor`` instead (it enables TLS by default) and give its
    ``.manager`` to :class:`CoffeaCasaVineWorkers`.
    """
    import ndcctools.taskvine as vine

    _check_port_free(port)
    return vine.Manager(port=port, name=name, ssl=True, **kwargs)


def _submit_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def vine_job_directives(manager_address, *, cores, memory_mb, disk_mb,
                        worker_image, idle_timeout, cluster_id, log_directory,
                        input_files=(), use_proxy=False, worker_env=None):
    """HTCondor submit directives for TaskVine workers (without site overrides)"""
    files = ", ".join(str(f) for f in input_files)
    log_directory = Path(log_directory)
    directives = {
        "universe": "docker",
        "docker_image": worker_image,
        # The image's entrypoint builds the vine_worker command from the job
        # ad; the executable itself is not run when it does.
        "executable": "/bin/true",
        "transfer_executable": False,
        "container_service_names": "vine",
        "vine_container_port": VINE_CONTAINER_PORT,
        "request_cpus": cores,
        "request_memory": memory_mb,
        # HTCondor's request_disk is in KiB
        "request_disk": disk_mb * 1024,
        "use_x509userproxy": use_proxy,
        "should_transfer_files": "YES",
        "when_to_transfer_output": "ON_EXIT",
        "transfer_output_files": "",
        # Spooled (condor_submit -spool): output comes back with
        # fetch_worker_logs(), so it can't be streamed.
        "output": str(log_directory / "vine-worker-$(ClusterId).$(ProcId).out"),
        "error": str(log_directory / "vine-worker-$(ClusterId).$(ProcId).err"),
        "stream_output": False,
        "stream_error": False,
        "+CoffeaCasaWorkerType": '"taskvine"',
        "+VineManagerAddress": f'"{manager_address}"',
        "+VineWorkerTimeout": int(idle_timeout),
        "+AccountingGroup": '"cms.other.coffea.$ENV(HOSTNAME)"',
        "+CoffeaCasaClusterId": f'"{cluster_id}"',
    }
    if files:
        directives["transfer_input_files"] = files
        directives["encrypt_input_files"] = files
    if worker_env:
        # Outer quotes select HTCondor's space-separated environment syntax
        directives["environment"] = '"' + quote_environment(worker_env) + '"'
    return directives


class CoffeaCasaVineWorkers:
    """TaskVine workers submitted to HTCondor for a manager in this notebook.

    Parameters
    ----------
    manager : ndcctools.taskvine.Manager
        The manager workers connect to; it must use TLS (``ssl=True``) and
        listen on the port routed to the notebook (see :func:`vine_manager`).
    cores : int, default 1
        Cores per worker.
    memory_mb, disk_mb : int, default 4000 / 8000
        Memory and disk per worker, in MB.
    worker_image : str, optional
        Worker image; defaults to ``jobqueue.coffea-casa.worker-image``.
    idle_timeout : int, default 900
        Seconds a worker waits without work before it exits.
    log_directory : str or Path, optional
        Where :meth:`fetch_worker_logs` puts worker stdout/stderr.

    Example
    -------
    >>> from vine_reduce.taskvine_distributor import TaskVineDistributor
    >>> distributor = TaskVineDistributor(port=8786)
    >>> workers = CoffeaCasaVineWorkers(distributor.manager, cores=4,
    ...                                 memory_mb=8000, disk_mb=16000)
    >>> workers.submit(10)
    >>> ...  # run the analysis
    >>> workers.close()
    """

    def __init__(self, manager, *, cores=1, memory_mb=4000, disk_mb=8000,
                 worker_image=None, idle_timeout=900, log_directory=None):
        if not getattr(manager, "using_ssl", False):
            raise ValueError(
                "The TaskVine manager must use TLS (ssl=True): coffea-casa "
                "workers always connect with --ssl.")
        self.manager_address = f"{external_host()}:{manager.port}"
        self.cluster_id = uuid.uuid4().hex
        self.log_directory = Path(
            log_directory
            or dask.config.get(f"jobqueue.{CONFIG_NAME}.log-directory", None)
            or DEFAULT_LOG_DIR)
        image = worker_image or dask.config.get(f"jobqueue.{CONFIG_NAME}.worker-image")
        if not image:
            raise ValueError("No worker image: pass worker_image= or set "
                             f"jobqueue.{CONFIG_NAME}.worker-image")

        input_files = [p for p in (bearer_token_path(),) if p]
        directives = vine_job_directives(
            self.manager_address,
            cores=cores, memory_mb=memory_mb, disk_mb=disk_mb,
            worker_image=image, idle_timeout=idle_timeout,
            cluster_id=self.cluster_id, log_directory=self.log_directory,
            input_files=input_files,
            use_proxy=x509_user_proxy_path() is not None,
            worker_env=worker_passthrough_env(),
        )
        # Site settings (accounting group, ...) apply as for Dask workers,
        # but can't turn token encryption off.
        directives.update(
            dask.config.get(f"jobqueue.{CONFIG_NAME}.job-extra-directives", {}) or {})
        self.directives = _keep_files_encrypted(directives, input_files)
        self.job_ids = []

    def submit_description(self, n):
        """The HTCondor submit description for `n` workers"""
        lines = [f"{k} = {_submit_value(v)}" for k, v in self.directives.items()]
        return "\n".join(lines + [f"queue {int(n)}", ""])

    def submit(self, n=1):
        """Submit `n` workers; returns the HTCondor cluster id"""
        self.log_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".sub", delete=False) as f:
            f.write(self.submit_description(n))
        try:
            result = subprocess.run(["condor_submit", "-spool", f.name],
                                    capture_output=True, text=True)
        finally:
            Path(f.name).unlink()
        if result.returncode != 0:
            raise RuntimeError(f"condor_submit failed: {result.stderr.strip()}")
        match = re.search(r"submitted to cluster (\d+)", result.stdout)
        if match:
            self.job_ids.append(int(match.group(1)))
        return int(match.group(1)) if match else None

    def close(self):
        """Remove this object's workers from HTCondor"""
        result = subprocess.run(
            ["condor_rm", "-constraint", f'CoffeaCasaClusterId == "{self.cluster_id}"'],
            capture_output=True, text=True)
        if result.returncode != 0 and "no jobs" not in (result.stderr + result.stdout).lower():
            print(f"condor_rm failed: {result.stderr.strip()}")

    def fetch_worker_logs(self):
        """Copy stdout/stderr of finished workers back from HTCondor.

        Returns the ``vine-worker-*`` files in ``log_directory``, newest first.
        Workers removed with :meth:`close` lose their spooled output.
        """
        return [p for p in fetch_spooled_logs(f'"{self.cluster_id}"', self.log_directory)
                if p.name.startswith("vine-worker-")]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
