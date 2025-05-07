"""
Gather the .json files and download them locally

Note that the analyzer is run in a different environment with python 3.8.
It CANNOT have any dependencies other than the idmtools package and basic python libraries
"""

import json
import os
from idmtools.entities import IAnalyzer
from idmtools.entities.iworkflow_item import IWorkflowItem
from idmtools.entities.simulation import Simulation
from idmtools.core.platform_factory import Platform
from idmtools.analysis.platform_anaylsis import PlatformAnalysis
from typing import Any, Union, Optional, List, Dict


class DataBrickAnalyzer(IAnalyzer):
    """
    Accumulate files in .json with experiment tags
    """ 
    def __init__(self, filenames: List[str] = ["results.json"]):
        super().__init__(filenames=filenames)

    def map(
        self, data: Dict[str, Any], item: Union["IWorkflowItem", "Simulation"]
    ) -> Any:
        data_dict = {}
        data_dict.update(data[self.filenames[0]])
        # for filename in self.filenames:
        #     data_dict.update(data[filename])
        data_dict["tags"] = item.tags

        return data_dict

    def reduce(self, all_data: Dict[Union["IWorkflowItem", "Simulation"], Any]) -> Any:
        output_dict = dict()

        for _, (s, v) in enumerate(all_data.items()):
            entry = {}
            tags = v.pop("tags")
            entry.update(tags)
            entry.update(v)
            output_dict[str(s.uid)] = entry

        # write data
        with open("data_brick.json", "w") as fp:
            json.dump(output_dict, fp)

def gather(experiment_id: str, output: Optional[str] = None):
    """Gather data from a COMPS experiment.
    
    Args:
        experiment_id: The experiment ID or the filename of the experiment ID file
        output: Optional path to save results to a file
        
    Returns:
        List of result data if output is None, otherwise None
    """
    platform = Platform("CALCULON")

    # Parse experiment ID
    if os.path.exists(experiment_id):
        with open(experiment_id, "r") as f:
            experiment_id = f.read()
    if "::Experiment" in experiment_id:
        experiment_id = experiment_id.split("::")[0]

    # Setup analyzers
    analysis = PlatformAnalysis(
        platform=platform,
        experiment_ids=[experiment_id],
        analyzers=[DataBrickAnalyzer],
        analyzers_args=[{}],
        analysis_name="SSMT analysis",
    )
    analysis.analyze(check_status=True)
    wi = analysis.get_work_item()    
    
    # Download reduced output and delete work item
    with Platform("SLURM") as platform:
        resp_dict = platform.get_files(wi, ["data_brick.json"])
        ret_val = json.loads(resp_dict["data_brick.json"].decode())
        results = len(ret_val)*[None]
        for i, v in enumerate(ret_val.values()):
            if "trial_index" in v:
                trial_index = int(v.pop("trial_index"))
            else:
                trial_index = i
            # do not save the task type
            v.pop("task_type")
            results[trial_index] = {k:v_list for k, v_list in v.items()}

    if output is not None and output != "NONE":
        print(f"Saving results to {output}")
        with open(output, "w") as f:
            json.dump(results, f)
        return None
    else:
        print(f"Returning results")
        return results