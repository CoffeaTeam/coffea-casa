import os
import re
import sys

import dask
from dask_jobqueue.core import cluster_parameters, job_parameters
from dask_jobqueue.htcondor import HTCondorCluster, HTCondorJob

from distributed.utils import import_term


class CoffeaCasaJob(HTCondorJob):
    _script_template = """
%(shebang)s

%(job_header)s

Environment = "%(quoted_environment)s"
Arguments = "%(quoted_arguments)s"
Executable = %(executable)s

Queue
""".lstrip()

    submit_command = "condor_submit -spool"

    def __init__(
        self,
        scheduler=None,
        name=None,
        worker_image=None,
        protocol=None,
        scheduler_port=8787,
        config_name=None,
        **base_class_kwargs
    ):   
        # Instantiate args and parameters from parent abstract class
        super().__init__(
            scheduler=scheduler, name=name, config_name=config_name, **base_class_kwargs
        )
        # Docker: Dask worker Docker image is "must".
        if worker_image is None:
            raise ValueError(
                "You must specify worker image for Coffea-casa analysis ``worker_image='coffeateam/coffea-casa:latest'``"
        )
        if worker_image:
            self.worker_image = worker_image
        # Scheduler port:
        if scheduler_port:
            self.scheduler_port = scheduler_port
        # Networking: we need to have external IP (manadatory for Dask worker<->scheduler comunication)
        try:
            external_ip = os.environ['HOST_IP']
        except KeyError:
            print("Please check with system administarator why external IP was not assigned for you.")
            sys.exit(1)
        # Networking: Special string case for external IP (external_ip_string will be used for scheduler_options
        if external_ip:
            external_address = str(protocol)+str(external_ip)+':'+str(scheduler_port)
            external_ip_string = '"'+ external_address+'"'
            self.external_address = external_address
            self.external_ip = external_ip
            
        # HTCondor: we have a custom job_extra for CoffeaCasaCluster
        # Networking: add DaskScheduleAdress. For this we extend job header with job_header_extra
        job_extra_default = {
            "universe": "docker",
            "docker_image": self.worker_image, 
            "container_service_names": "dask",
            "dask_container_port": "8787",
            "should_transfer_files": "YES",
            "when_to_transfer_output": "ON_EXIT",
            "transfer_input_files": "/etc/cmsaf-secrets/xcache_token,/etc/cmsaf-secrets/ca.pem,/etc/cmsaf-secrets/hostcert.pem",
            "encrypt_input_files": "/etc/cmsaf-secrets/xcache_token,/etc/cmsaf-secrets/ca.pem,/etc/cmsaf-secrets/hostcert.pem",
            "Stream_Output": False,
            "Stream_Error": False,
            "+DaskSchedulerAddress": external_ip_string,
        }
        self.job_extra_default=job_extra_default
        self.job_header_dict.update(self.job_extra_default)
        
        # Lets check if somebody else added already a job_extra
        job_extra = base_class_kwargs.get("job_extra", None)
        # lets check dask config environment
        if job_extra is None:
            self.job_extra = dask.config.get(
            "jobqueue.%s.job-extra" % self.config_name, {})
        else:
            self.job_extra = job_extra
        
        if self.job_extra:
                self.job_header_dict.update(self.job_extra)
  
        # Env_extra          
        env_extra = base_class_kwargs.get("env_extra", None)
        # lets check dask config environment   
        if env_extra is None:
            env_extra = dask.config.get(
                "jobqueue.%s.env-extra" % self.config_name, default=[]
                )
        self.env_dict = self.env_lines_to_dict(env_extra)

    
    # Update job script       
    def job_script(self):
        """ Update a job submission script """
        quoted_arguments = super(CoffeaCasaJob, self).quote_arguments(["-c", self._command_template])
        quoted_environment =  super(CoffeaCasaJob, self).quote_environment(self.env_dict)
        job_header_lines = "\n".join(
            "%s = %s" % (k, v) for k, v in self.job_header_dict.items()
        )
        return self._script_template % {
            "shebang": self.shebang,
            "job_header": job_header_lines,
            "quoted_environment": quoted_environment,
            "quoted_arguments": quoted_arguments,
            "executable": self.executable,
        }


class CoffeaCasaCluster(HTCondorCluster):
    __doc__ = """ Launch Dask on an Coffea Casa k8s HTCondor cluster
    Parameters
    ----------
    cores=24, memory="4GB", disk="4GB", worker_image="coffeateam/coffea-casa:latest"
    disk : str
        Total amount of disk per job
    job_extra : dict
        Extra submit file attributes for the job
    {job}
    {cluster}
    Examples
    --------
    >>> from coffea_casa.coffea_casa import CoffeaCasaCluster
    >>> cluster = CoffeaCasaCluster(cores=24, memory="4GB", disk="4GB", worker_image="coffeateam/coffea-casa:latest")
    >>> cluster.scale(jobs=10)  # ask for 10 jobs
    >>> from dask.distributed import Client
    >>> client = Client(cluster)
    This also works with adaptive clusters.  This automatically launches and kill workers based on load.
    >>> cluster.adapt(maximum_jobs=20)
    """.format(
        job=job_parameters, cluster=cluster_parameters
    )
    job_cls=CoffeaCasaJob
    
    #scheduler_options=None,
    def __init__(
        self,
        job_cls = CoffeaCasaJob,
        scheduler_options=None,
        dashboard_address=8786,
        scheduler_spec=None,
        protocol = "tcp://",
        security=None,
        **job_class_kwargs
    ):   
        # Instantiate args and parameters from parent abstract class
        super().__init__(
            scheduler_spec=scheduler_spec, scheduler_options=scheduler_options, security=security, protocol=protocol, **job_class_kwargs
        )
        
        # Add Custom scheduler options    
        self.protocol = protocol
        # Protocol: We need to have for dask not "tls://" but "tls"
        #if re.match(r'://', self.protocol):
        self.protocol_dask = self.protocol.replace("://","")
        #else:
        #    self.protocol_dask = self.protocol
        
        self.dashboard_address = dashboard_address
        
        default_job_cls = getattr(type(self), "job_cls", None)
        
        scheduler_options_extra={
            "protocol": self.protocol_dask,
            "dashboard_address":  self.dashboard_address,
            "port": "8787",
            # how to get external address from class?
            
            #"external_address":  job_class_kwargs.get("external_address", None),
        }
        self.scheduler_spec["options"].update(scheduler_options_extra)

        print(self.scheduler_spec)
        
        if scheduler_options:
            scheduler_options = scheduler_options
            self.scheduler_spec["options"].update(scheduler_options)
