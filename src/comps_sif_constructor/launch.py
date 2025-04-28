"""
Module for running COMPS experiments with configuration support.
"""
import json
from dataclasses import dataclass, field
from typing import Optional

from idmtools.assets import AssetCollection, Asset
from idmtools.entities.command_task import CommandTask


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
    for k,v in kwargs.items():
        simulation.task.set_parameter(k, v)
    return kwargs