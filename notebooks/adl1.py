import os
import dask

from distributed.security import Security
from coffea import hist
from coffea.analysis_objects import JaggedCandidateArray
import coffea.processor as processor

from dask.distributed import Client, LocalCluster
from dask_jobqueue import HTCondorCluster
from dask_jobqueue.htcondor import HTCondorJob

fileset = {
    'Jets': { 'files': ['root://eospublic.cern.ch//eos/root-eos/benchmark/Run2012B_SingleMu.root'],
             'treename': 'Events'
            }
}

# This program plots an event-level variable (in this case, MET, but switching it is as easy as a dict-key change). It also demonstrates an easy use of the book-keeping cutflow tool, to keep track of the number of events processed.
# The processor class bundles our data analysis together while giving us some helpful tools.  It also leaves looping and chunks to the framework instead of us.
class METProcessor(processor.ProcessorABC):
    def __init__(self):
        # Bins and categories for the histogram are defined here. For format, see https://coffeateam.github.io/coffea/stubs/coffea.hist.hist_tools.Hist.html && https://coffeateam.github.io/coffea/stubs/coffea.hist.hist_tools.Bin.html
        self._columns = ['MET_pt']
        dataset_axis = hist.Cat("dataset", "")
        MET_axis = hist.Bin("MET", "MET [GeV]", 50, 0, 100)
        # The accumulator keeps our data chunks together for histogramming. It also gives us cutflow, which can be used to keep track of data.
        self._accumulator = processor.dict_accumulator({
            'MET': hist.Hist("Counts", dataset_axis, MET_axis),
            'cutflow': processor.defaultdict_accumulator(int)
        })

    @property
    def accumulator(self):
        return self._accumulator

    @property
    def columns(self):
        return self._columns

    def process(self, df):
        output = self.accumulator.identity()
        # This is where we do our actual analysis. The df has dict keys equivalent to the TTree's.
        dataset = df['dataset']
        MET = df['MET_pt']
        # We can define a new key for cutflow (in this case 'all events'). Then we can put values into it. We need += because it's per-chunk (demonstrated below)
        output['cutflow']['all events'] += MET.size
        output['cutflow']['number of chunks'] += 1
        # This fills our histogram once our data is collected. Always use .flatten() to make sure the array is reduced. The output key will be as defined in __init__ for self._accumulator; the hist key ('MET=') will be defined in the bin.
        output['MET'].fill(dataset=dataset, MET=MET.flatten())
        return output

    def postprocess(self, accumulator):
        return accumulator
    
    
sec_dask = Security(tls_ca_file='/etc/cmsaf-secrets/ca.pem',
               tls_worker_cert='/etc/cmsaf-secrets/usercert.pem',
               tls_worker_key='/etc/cmsaf-secrets/usercert.pem',
               tls_client_cert='/etc/cmsaf-secrets/usercert.pem',
               tls_client_key='/etc/cmsaf-secrets/usercert.pem',
               tls_scheduler_cert='/etc/cmsaf-secrets/hostcert.pem',
               tls_scheduler_key='/etc/cmsaf-secrets/hostcert.pem',
               require_encryption=True)

HTCondorJob.submit_command = "condor_submit -spool"

cluster = HTCondorCluster(cores=4,
                          memory="2GB",
                          disk="1GB",
                          log_directory="logs",
                          silence_logs="DEBUG",
                          scheduler_options= {"dashboard_address":"8786", "port":8787, "external_address": "129.93.183.33:8787"},
                          # HTCondor submit script
                          job_extra={"universe": "docker",
                                     # To be used with coffea-casa:0.1.11
                                     "encrypt_input_files": "/etc/cmsaf-secrets/xcache_token",
                                     #"docker_network_type": "host",
                                     "docker_image": "coffeateam/coffea-casa-analysis:0.1.24", 
                                     "container_service_names": "dask",
                                     "dask_container_port": "8787",
                                     "should_transfer_files": "YES",
                                     "when_to_transfer_output": "ON_EXIT",
                                     "+DaskSchedulerAddress": '"129.93.183.33:8787"',
                                    })

cluster.adapt(minimum_jobs=2, maximum_jobs=10)  # auto-scale between 5 and 10 jobs (interval=500, wait_count=1, target_duration=10 )

client = Client(cluster)

dask.config.config

exe_args = {
        'client': client,
    }

output = processor.run_uproot_job(fileset,
                                treename = 'Events',
                                processor_instance = METProcessor(),
                                executor = processor.dask_executor,
                                executor_args = exe_args
                                )

# Generates a 1D histogram from the data output to the 'MET' key. fill_opts are optional, to fill the graph (default is a line).
hist.plot1d(output['MET'], overlay='dataset', fill_opts={'edgecolor': (0,0,0,0.3), 'alpha': 0.8})

# Easy way to print all cutflow dict values. Can just do print(output['cutflow']["KEY_NAME"]) for one.
for key, value in output['cutflow'].items():
    print(key, value)