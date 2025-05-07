""" 
This script is used to create a Singularity image file from a Singularity definition file.

Usage:
    python -m comps_sif_constructor.create_sif -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
    comps_sif_constructor -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
"""

import sys
import traceback

from idmtools.core.platform_factory import Platform
from idmtools_platform_comps.utils.singularity_build import SingularityBuildWorkItem
from idmtools.assets import Asset

from . import defaults

# Import the create_sif functionality from cli.py
def create_sif(definition_file=defaults.DEFINITION_FILE, output_id=defaults.SIF_ID_FILE, image_name=defaults.SIF_FILE, work_item_name=defaults.WORK_ITEM_NAME, requirements=defaults.REQUIREMENTS):
    platform = Platform("CALCULON")
    sbi = SingularityBuildWorkItem(
        name=work_item_name,
        definition_file=definition_file,
        image_name=image_name,
    )
    if requirements is not None:
        sbi.assets.add_or_replace_asset(Asset(filename=requirements))
    sbi.tags = dict(my_key="my_value")
    try:
        sbi.run(wait_until_done=True, platform=platform)
    except AttributeError as e:
        print(f"AttributeError during COMPS build: {e}")
        traceback.print_exc()
        sys.exit(1)

    if sbi.succeeded:
        sbi.asset_collection.to_id_file(output_id)
