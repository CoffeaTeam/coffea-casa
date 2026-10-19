"""Count running work as activity, so the idle culler doesn't stop busy servers.

JupyterHub's idle culler stops a server when it reports no activity for a while
(an hour by default). jupyter_server only counts browser requests, terminal
traffic while a browser is attached and kernel messages as activity, so a long
script running in a terminal after the browser was closed, or a notebook cell
that runs for hours without printing, looks idle and gets killed (#422).

This server extension checks periodically whether a terminal has a command
running (its shell has child processes) or a kernel is busy, and if so records
activity under a setting ending in ``_last_activity``, which jupyter_server
includes in the activity it reports to the hub. Servers with nothing running
are still culled as before.

Enabled by /etc/jupyter/jupyter_server_config.d/coffea_casa_activity.json.
"""
import datetime
import os

import psutil
from tornado.ioloop import PeriodicCallback

# Any settings key ending in "_last_activity" counts (ServerApp.last_activity)
SETTING = "coffea_casa_running_work_last_activity"
INTERVAL_S = float(os.environ.get("COFFEA_CASA_ACTIVITY_INTERVAL", 60))


def _jupyter_server_extension_points():
    return [{"module": __name__}]


def terminal_busy(terminal_manager):
    """Whether any terminal's shell has a command (child process) running."""
    if terminal_manager is None:
        return False
    for term in list(terminal_manager.terminals.values()):
        try:
            if psutil.Process(term.ptyproc.pid).children():
                return True
        except psutil.Error:  # terminal exited meanwhile
            continue
    return False


def kernel_busy(kernel_manager):
    """Whether any kernel is executing code."""
    for kernel_id in list(kernel_manager.list_kernel_ids()):
        try:
            if kernel_manager.get_kernel(kernel_id).execution_state == "busy":
                return True
        except KeyError:  # kernel shut down meanwhile
            continue
    return False


def _load_jupyter_server_extension(serverapp):
    pass


async def _start_jupyter_server_extension(serverapp):
    settings = serverapp.web_app.settings

    def check():
        try:
            if (kernel_busy(settings["kernel_manager"])
                    or terminal_busy(settings.get("terminal_manager"))):
                settings[SETTING] = datetime.datetime.now(datetime.timezone.utc)
        except Exception:
            serverapp.log.exception("coffea_casa_activity: activity check failed")

    callback = PeriodicCallback(check, INTERVAL_S * 1000)
    callback.start()
    settings["coffea_casa_activity_callback"] = callback
    serverapp.log.info("coffea_casa_activity: counting running terminal commands "
                       "and busy kernels as activity (every %ss)", INTERVAL_S)
