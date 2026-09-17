"""CoffeaCasa - Dask cluster management for CMS Analysis Facilities"""

# Registers the jobqueue.coffea-casa dask-config defaults (worker-image,
# job-extra-directives, ...) via dask.config.update_defaults(). The coffea-casa
# image also gets these from the static jobqueue-coffea-casa.yaml it ships
# under DASK_ROOT_CONFIG, which dask's own config loader reads natively - but
# a plain `pip install coffea-casa` elsewhere has no such env var, so
# CoffeaCasaCluster() would otherwise fail with KeyError: 'coffea-casa' on
# first use. Import for side effects only.
from . import config  # noqa: F401

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
