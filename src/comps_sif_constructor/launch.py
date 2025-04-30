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
    A class to handle COMPS experiment deployment and management. An experiment is a collection of trials (e.g., simulations).
    """
    def __init__(self, name='python', num_threads=1, priority="AboveNormal", node_group="idm_48cores", 
                 sif_filename="default.sif", sif_id_file="sif.id"):
        """
        Initialize the CompsExperiment.
        
        Args:
            name: Name of the experiment
            num_threads: Number of threads to use
            priority: Priority level for the experiment
            node_group: Node group to use
            sif_filename: Name of the singularity image file
            sif_id_file: Path to the asset ID file
        """
        self.name = name
        self.num_threads = num_threads
        self.priority = priority
        self.node_group = node_group
        self.num_trials = None
        self.trials_content = None
        self.run_script = None
        self.remote_script = None
        self.sif_filename = sif_filename
        self.sif_id_file = sif_id_file

    def plan(self, file_path=None, content: Optional[list[dict] | dict] = None):
        """
        Plan the experiment by setting up the trials data.
        
        Args:
            file_path: Path to an existing trials.jsonl file or the content as a string
            content: A list of dictionaries or a dictionary of lists to be used as trials data
            
        Returns:
            self: For method chaining
        
        Note:
            Either trials or content must be provided
        """
        if file_path is not None:
            if isinstance(file_path, str) and file_path.endswith('.jsonl'):
                # If trials is a file path, read the file
                with open(file_path, 'r') as f:
                    self.trials_content = f.read()
                    # Count the number of lines to determine num_trials
                    num_lines = len([line for line in self.trials_content.splitlines() if line.strip()])
                    self.num_trials = num_lines
            else:
                # Assume trials is the content directly
                self.trials_content = file_path
                # Count the number of lines to determine num_trials
                num_lines = len([line for line in self.trials_content.splitlines() if line.strip()])
                self.num_trials = num_lines
        elif content is not None:
            # Convert list of dicts 
            self.trials_content = ""
            if isinstance(content, list):
                self.num_trials = len(content)
                for trial in content:
                    self.trials_content += json.dumps(trial) + "\n"
            elif isinstance(content, dict):
                self.num_trials = len(list(content.items()))
                for key, value in content.items():
                    self.trials_content += json.dumps({key: value}) + "\n"
            else:
                raise ValueError("Content must be a list of dictionaries or a dictionary of lists")
        else:
            raise ValueError("Either trials or content must be provided")
        
        return self

    def deploy(self):
        """Deploy the experiment to COMPS."""
        # Create a platform to run the workitem
        platform = Platform("CALCULON", priority=self.priority)

        # create commandline input for the task
        cmdline = f"singularity exec ./Assets/{self.sif_filename} bash run.sh"
        command = CommandLine(cmdline)
        task = ConfigCommandTask(command=command)

        # Add our image
        task.common_assets.add_assets(AssetCollection.from_id_file(self.sif_id_file))

        # Add simulation script
        task.transient_assets.add_or_replace_asset(Asset(filename="run.sh"))
        
        # Add the trials JSONL data
        if self.trials_content is not None:
            task.transient_assets.add_or_replace_asset(Asset(filename="trials.jsonl", content=self.trials_content))
        else:
            # For backward compatibility, try to add an existing file
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
            node_group_name=self.node_group,
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