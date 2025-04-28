"""
https://github.com/gatesfoundation/GEOMED24/blob/main/calibration/calib_hartmann/run_service.py
"""
import os
import json

from idmtools.assets import AssetCollection, Asset
from idmtools.core.platform_factory import Platform
from idmtools.entities import CommandLine
from idmtools.builders import SimulationBuilder
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations
from idmtools_platform_comps.utils.scheduling import add_schedule_config

from comps_sif_constructor.launch import ConfigCommandTask, update_parameter_callback

def deploy(name='python', num_threads=1, priority="AboveNormal"):
    """ Deploy the experiment to COMPS """
    
    # Create a platform to run the workitem
    platform = Platform("CALCULON", priority=priority)

    # create commandline input for the task
    cmdline = "singularity exec ./Assets/python_0.0.1.sif bash run.sh"
    command = CommandLine(cmdline)
    task = ConfigCommandTask(command=command)

    # Add our image
    task.common_assets.add_assets(AssetCollection.from_id_file("sif.id"))

    # Add simulation script
    task.transient_assets.add_or_replace_asset(Asset(filename="run.sh"))

    # Add analysis scripts
    sb = SimulationBuilder()
    sb.add_sweep_definition(lambda simulation, a: None, range(1,2))
  
    ts = TemplatedSimulations(base_task=task)
    ts.add_builder(sb)
    add_schedule_config(
        ts,
        command=cmdline,
        NumNodes=1,
        num_cores=num_threads,
        node_group_name="idm_48cores",
        Environment={"NUMBA_NUM_THREADS": str(num_threads),
                     "PYTHONPATH": ".:./Assets"},
    )
    experiment = Experiment.from_template(ts, name=f"{name}")
    experiment.run(wait_until_done=True, scheduling=True)

    if experiment.succeeded:
        # Setup analyzers
        experiment.to_id_file("experiment.id")
        # print
        print(f"Experiment {experiment.id} succeeded")
    else:
        raise RuntimeWarning("Experiment failed")

if __name__ == "__main__":
    # Change directory to the location of this file
    os.chdir(os.path.dirname(__file__))

    deploy(name='python', num_threads=1, priority="AboveNormal")
