"""Dask worker preload: make a shipped env reachable at its original path.

A shipped conda env is unpacked into the HTCondor job's scratch directory, so
it lives at a different path on the worker than in the notebook. Paths into
the env that were resolved in the notebook (e.g. a package's data files) and
sent to the workers then don't exist there. CoffeaCasaCluster sets
COFFEA_CASA_ENV_PREFIX to the env's original path and loads this module in
every worker, which links that path to the unpacked env.
"""
import logging
import os
import sys
from pathlib import Path

PREFIX_ENV_VAR = "COFFEA_CASA_ENV_PREFIX"

logger = logging.getLogger(__name__)


def link_original_prefix(original, actual=None):
    """Make ``original`` point to ``actual`` (default: this Python's prefix).

    Returns "same" if ``original`` already resolves to ``actual``, "linked"
    if a symlink was created, "exists" if something else is already there
    and "failed" if the link can't be created. Never raises.
    """
    original = Path(original)
    actual = Path(actual or sys.prefix).resolve()
    try:
        if original.resolve() == actual:
            return "same"
        if original.exists() or original.is_symlink():
            logger.warning("Not linking the shipped env to %s: the path already "
                           "exists on this worker", original)
            return "exists"
        original.parent.mkdir(parents=True, exist_ok=True)
        original.symlink_to(actual, target_is_directory=True)
    except FileExistsError:  # created meanwhile by another process
        return "same" if original.resolve() == actual else "exists"
    except OSError as e:
        logger.warning("Could not link the shipped env to %s: %s", original, e)
        return "failed"
    logger.info("Linked %s to the shipped env at %s", original, actual)
    return "linked"


def dask_setup(worker):
    original = os.environ.get(PREFIX_ENV_VAR)
    if original:
        link_original_prefix(original)
