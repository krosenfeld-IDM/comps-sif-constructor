""" 
This script is used to create a Singularity image file from a Singularity definition file.

Usage:
    python -m comps_sif_constructor.create_sif -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
    comps_sif_constructor -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
"""

import click
from idmtools.core.platform_factory import Platform
from idmtools_platform_comps.utils.singularity_build import SingularityBuildWorkItem
from idmtools.assets.file_list import FileList
import traceback
import sys

def create_sif(definition_file, output_id, image_name, work_item_name, requirements):
    kwargs = {}
    if requirements is not None:
        kwargs["asset_files"] = FileList(files_in_root=[requirements])

    platform = Platform("CALCULON")
    sbi = SingularityBuildWorkItem(
        name=work_item_name,
        definition_file=definition_file,
        image_name=image_name,
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
        sbi.asset_collection.to_id_file(output_id)

@click.command()
@click.option("--definition_file", "-d", type=str, help="Path to the Singularity definition file", default="lolcow.def")
@click.option("--output_id", "-o", type=str, help="(optional) Name out Asset id file", default="sif.id")
@click.option("--image_name", "-i", type=str, help="(optional) Name of the Singularity image file", default="lolcow_0.0.1.sif")
@click.option("--work_item_name", "-w", type=str, help="(optional) Name of the work item", default="Singularity Build")
@click.option("--requirements", "-r", type=str, help="(optional) Path to the requirements file", default=None)
def main(definition_file, output_id, image_name, work_item_name, requirements):
    create_sif(definition_file, output_id, image_name, work_item_name, requirements)

if __name__ == "__main__":
    main()
