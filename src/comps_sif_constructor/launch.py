"""
Module for running COMPS experiments with configuration support.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

from idmtools.assets import AssetCollection, Asset
from idmtools.entities.command_task import CommandTask
from idmtools.core.platform_factory import Platform
from idmtools.entities import CommandLine
from idmtools.builders import SimulationBuilder
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations
from idmtools_platform_comps.utils.scheduling import add_schedule_config

@dataclass
class ConfigCommandTask(CommandTask):
    """
    A specialized CommandTask that supports configuration parameters.
    
    This class extends CommandTask to provide configuration management capabilities,
    allowing parameters to be set and stored in a JSON file.
    """
    configfile_argument: Optional[str] = field(default="--config")

    def __init__(self, command):
        self.config = dict()
        CommandTask.__init__(self, command)

    def set_parameter(self, param_name, value):
        """
        Set a configuration parameter.
        
        Args:
            param_name: The name of the parameter
            value: The value to set
        """
        self.config[param_name] = value

    def gather_transient_assets(self) -> AssetCollection:
        """
        Gathers transient assets, primarily the settings.py file.

        Returns:
            AssetCollection: Transient assets containing the configuration.
        """
        # create a json string out of the dict self.config
        self.transient_assets.add_or_replace_asset(
            Asset(filename="trial_index.json", content=json.dumps(self.config))
        ) 

def update_parameter_callback(simulation, **kwargs):
    """
    Update the parameters for the simulation.
    """
    for k,v in kwargs.items():
        simulation.task.set_parameter(k, v)
    return kwargs

class CompsExperiment:
    """
    A class to handle COMPS experiment deployment and management.
    """
    def __init__(self, name='python', num_threads=1, priority="AboveNormal", num_trials=1, node_group="idm_48cores"):
        """
        Initialize the CompsExperiment.
        
        Args:
            name: Name of the experiment
            num_threads: Number of threads to use
            priority: Priority level for the experiment
            num_trials: Number of trials to run
            node_group: Node group to use
        """
        self.name = name
        self.num_threads = num_threads
        self.priority = priority
        self.num_trials = num_trials
        self.node_group = node_group

    def deploy(self):
        """Deploy the experiment to COMPS."""
        # Create a platform to run the workitem
        platform = Platform("CALCULON", priority=self.priority)

        # create commandline input for the task
        cmdline = "singularity exec ./Assets/python_0.0.1.sif bash run.sh"
        command = CommandLine(cmdline)
        task = ConfigCommandTask(command=command)

        # Add our image
        task.common_assets.add_assets(AssetCollection.from_id_file("sif.id"))

        # Add simulation script
        task.transient_assets.add_or_replace_asset(Asset(filename="run.sh"))
        # Add the trials (json Dict[list] with the values that can be indexed by the simulation for its parameter values.
        task.transient_assets.add_or_replace_asset(Asset(filename="trials.jsonl"))
        # Add the remote script that will run on COMPS
        task.transient_assets.add_or_replace_asset(Asset(filename="remote.py"))

        # Add analysis scripts
        sb = SimulationBuilder()
        sb.add_multiple_parameter_sweep_definition(
            lambda simulation, trial_index: update_parameter_callback(simulation, trial_index=trial_index),
            trial_index=[i for i in range(self.num_trials)]
    )
        ts = TemplatedSimulations(base_task=task)
        ts.add_builder(sb)
        add_schedule_config(
            ts,
            command=cmdline,
            NumNodes=1,
            num_cores=self.num_threads,
            node_group_name="idm_48cores",
            Environment={"NUMBA_NUM_THREADS": str(self.num_threads),
                        "PYTHONPATH": ".:./Assets"},
        )
        experiment = Experiment.from_template(ts, name=f"{self.name}")
        experiment.run(wait_until_done=True, scheduling=True)

        if experiment.succeeded:
            # Setup analyzers
            experiment.to_id_file("experiment.id")
            print(f"Experiment {experiment.id} succeeded")
            return experiment
        else:
            raise RuntimeWarning("Experiment failed")