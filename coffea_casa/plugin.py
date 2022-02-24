import os
import sys
import zipfile
import logging
import uuid
import subprocess

from distributed.diagnostics.plugin import NannyPlugin
from dask.utils import tmpfile

logger = logging.getLogger(__name__)


class DistributedEnvironmentPlugin(NannyPlugin):
    """A NannyPlugin to upload a local pip installable package to workers.
    Parameters
    ----------
    path: str
        A path to the pip installable directory to upload
    Examples
    --------
    >>> from distributed.diagnostics.plugin import DistributedEnvironmentPlugin
    >>> client.register_worker_plugin(DistributedEnvironmentPlugin("/path/to/directory"), nanny=True)  # doctest: +SKIP
    """

    def __init__(
        self,
        path,
        pip_options=None,
        restart=False,
        update_path=False,
        skip_words=(".git", ".github", ".pytest_cache", "tests", "docs"),
        skip=(lambda fn: os.path.splitext(fn)[1] == ".pyc",),
        extra_inputs=[],
    ):
        """
        Initialize the plugin by reading in the data from the given file.
        """
        path = os.path.expanduser(path)
        self.package = os.path.split(path)[-1]
        self.restart = restart
        self.update_path = update_path
        if pip_options is None:
            pip_options = []
        self.pip_options = pip_options
        self.extra_inputs = [os.path.split(x)[-1] for x in extra_inputs]

        self.name = "upload-directory-" + self.package

        with tmpfile(extension="zip") as fn:
            with zipfile.ZipFile(fn, "w", zipfile.ZIP_DEFLATED) as z:
                for root, dirs, files in os.walk(path):
                    for file in files:
                        filename = os.path.join(root, file)
                        if any(predicate(filename) for predicate in skip):
                            continue
                        dirs = filename.split(os.sep)
                        if any(word in dirs for word in skip_words):
                            continue

                        archive_name = os.path.relpath(
                            os.path.join(root, file), os.path.join(path, "..")
                        )
                        z.write(filename, archive_name)
                for fpath in extra_inputs:
                    fname = os.path.split(fpath)[-1]
                    z.write(fpath,fname)

            with open(fn, "rb") as f:
                self.data = f.read()

    def setup(self, nanny):
        # Copy the package to the worker machine
        logger.info("Entering plugin setup")
        logger.info("nanny.local_directory: %s",nanny.local_directory)
        logger.info("nanny.worker_dir: %s",nanny.worker_dir)
        fn = os.path.join(nanny.local_directory, f"tmp-{str(uuid.uuid4())}.zip")
        with open(fn, "wb") as f:
            f.write(self.data)

        with zipfile.ZipFile(fn) as z:
            z.extractall(path=nanny.local_directory)

        if self.update_path:
            if nanny.local_directory not in sys.path:
                sys.path.insert(0, nanny.local_directory)
            path = os.path.join(nanny.local_directory, self.package)
            if path not in sys.path:
                sys.path.insert(0, path)

        # Now try to pip install the package
        package_path = os.path.join(nanny.local_directory,self.package)
        logger.info("Installing the package: %s",self.package)
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "install"] + self.pip_options + [package_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
        returncode = proc.wait()

        if returncode:
            logger.error("Pip install failed with '%s'",stderr.decode().strip())
            return

        # Cleanup the zip file
        logger.info("Cleaning up temporary directory: %s",fn)
        os.remove(fn)

        return

    def teardown(self, nanny):
        for fname in self.extra_inputs:
            logger.info(f"Removing: {fname}")
            path = os.path.join(nanny.local_directory,fname)
            os.remove(path)
        logger.info("Uninstalling the package: %s",self.package)
        proc = subprocess.Popen(
            [sys.executable, "-m", "pip", "uninstall", self.package],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
        returncode = proc.wait()

        if returncode:
            logger.error("Pip uninstall failed with '%s'",stderr.decode().strip())
            return

        return
