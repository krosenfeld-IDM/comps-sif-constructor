""" 
This script is used to create a Singularity image file from a Singularity definition file.

Usage:
    python -m comps_sif_constructor.create_sif -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
    comps_sif_constructor -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
"""

import argparse
from idmtools.core.platform_factory import Platform
from idmtools_platform_comps.utils.singularity_build import SingularityBuildWorkItem
from idmtools.assets.file_list import FileList
import traceback
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--definition_file", "-d", type=str, help="Path to the Singularity definition file"
    )
    parser.add_argument(
        "--output_id", "-o", type=str, help="Name out Asset id file", default="sif.id"
    )
    parser.add_argument(
        "--image_name", "-i", type=str, help="Name of the Singularity image file", default="laser_0.0.1.sif"
    )
    parser.add_argument(
        "--work_item_name", "-w",
        type=str,
        help="Name of the work item",
        default="Singularity Build",
    )
    parser.add_argument("--requirements", "-r", type=str, help="Path to the requirements file", default=None)
    args = parser.parse_args()

    kwargs = {}
    if args.requirements is not None:
        kwargs["asset_files"] = FileList(files_in_root=[args.requirements])

    platform = Platform("CALCULON")
    sbi = SingularityBuildWorkItem(
        name=args.work_item_name,
        definition_file=args.definition_file,
        image_name=args.image_name,
        **kwargs
    )
    sbi.tags = dict(my_key="my_value")
    try:
        sbi.run(wait_until_done=True, platform=platform)
    except AttributeError as e:
        print(f"AttributeError during COMPS build: {e}")
        traceback.print_exc()
        sys.exit(1)

    if sbi.succeeded:
        sbi.asset_collection.to_id_file(args.output_id)

if __name__ == "__main__":
    main()
