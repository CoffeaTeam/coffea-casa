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
from ._version import version as __version__

__all__ = [
    'CoffeaCasaCluster',
    'CoffeaCasaJob',
    'bearer_token_path',
    'x509_user_proxy_path',
    'security_obj',
    "DistributedEnvironmentPlugin",
    "start_remote_debugger",
]

__version__ = '2026.02.19'