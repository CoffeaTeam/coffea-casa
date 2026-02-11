import json
import subprocess
from dask.distributed import get_worker, print as dprint


def vscode_debug_config_on_worker() -> str:
    """
    Automatically generates the VSCode debug `launch.json` for HTCondor dask-workers.
    """
    worker = get_worker()

    cmd = "less $PWD/.job.ad | grep 'nanny_HostPort = '"
    out = subprocess.check_output(cmd, shell=True).decode("utf-8")
    debug_port = int(out.removeprefix("nanny_HostPort = "))

    vscode_cfg = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": f"Python Debugger: Remote Attach @{worker.host}",
                "justMyCode": True,
                "type": "debugpy",
                "request": "attach",
                "connect": {
                    "host": worker.host,
                    "port": debug_port,
                },
                "pathMappings": [
                    {
                        "localRoot": "${workspaceFolder}",
                        "remoteRoot": worker.local_directory,
                    }
                ]
            }
        ]
    }
    return json.dumps(vscode_cfg, indent=2)


_already_listening = False


def start_remote_debugger(
    msg: str = "Starting debug server...",
    tcp_host: str = "0.0.0.0",
    tcp_port: int = 8001,
) -> None:
    """
    Parameters
    ----------
    msg: str
        A msg to be printed when starting the debug server
    tcp_host: str
        The host address of the debugpy server that's running inside the HTCondor Job. Should be '0.0.0.0' usually.
    tcp_port: int
        The host port that's possible to listen to. Should be '8001' usually.

    Examples
    --------
    >>> from coffea_casa import start_remote_debugger
    >>> def analysis():
            ...
            # first start the debugger (it waits for a client connection), then drop into the breakpoint
            start_remote_debugger(); breakpoint()
            ...
    """
    import debugpy

    dprint(msg, flush=True)
    dprint(
        "Start a VSCode server session with coffea-casa's launcher, \
and copy & paste the following config into VSCode's built-in debugger (adjust as necessary):",
        flush=True,
    )
    dprint(vscode_debug_config_on_worker(), flush=True)

    global _already_listening
    if not _already_listening:
        debugpy.listen((tcp_host, tcp_port))
        _already_listening = True

    debugpy.wait_for_client()
