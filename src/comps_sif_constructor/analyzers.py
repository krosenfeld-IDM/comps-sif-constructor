import json
from idmtools.entities import IAnalyzer
from idmtools.entities.iworkflow_item import IWorkflowItem
from idmtools.entities.simulation import Simulation
from typing import Dict, Any, Union, Optional


class DataBrickAnalyzer(IAnalyzer):
    """
    Accumulate files in .json with experiment tags
    """
    def __init__(self):
        super().__init__(filenames=["results.json"])

    def map(
        self, data: Dict[str, Any], item: Union["IWorkflowItem", "Simulation"]
    ) -> Any:
        data_dict = {}
        data_dict.update(data[self.filenames[0]])
        data_dict["tags"] = item.tags

        return data_dict

    def reduce(self, all_data: Dict[Union["IWorkflowItem", "Simulation"], Any]) -> Any:
        output_dict = dict()

        for ix, (s, v) in enumerate(all_data.items()):
            entry = {}
            tags = v.pop("tags")
            entry.update(tags)
            entry.update(v)
            output_dict[str(s.uid)] = entry

        # write data
        with open("data_brick.json", "w") as fp:
            json.dump(output_dict, fp)