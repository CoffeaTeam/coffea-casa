"""CoffeaCasa - Dask cluster management for CMS Analysis Facilities"""

from .coffea_casa import (
    CoffeaCasaCluster,
    CoffeaCasaJob,
    bearer_token_path,
    x509_user_proxy_path,
    security_obj,
)
from .plugin import DistributedEnvironmentPlugin
from .remote_debug import start_remote_debugger
try:
    from ._version import version as __version__
except ImportError:  # package not built with hatch-vcs (e.g. raw checkout)
    __version__ = "0.0.0+unknown"

__all__ = [
    'CoffeaCasaCluster',
    'CoffeaCasaJob',
    'bearer_token_path',
    'x509_user_proxy_path',
    'security_obj',
    "DistributedEnvironmentPlugin",
    "start_remote_debugger",
]
