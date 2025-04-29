""" 
This script is used to create a Singularity image file from a Singularity definition file.

Usage:
    python -m comps_sif_constructor.create_sif -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
    comps_sif_constructor -d <path_to_definition_file> -o <output_id> -i <image_name> -w <work_item_name> [-r <requirements_file>]
"""

# Import the create_sif functionality from cli.py
from comps_sif_constructor.cli import create_sif, create_sif_func, main

if __name__ == "__main__":
    main()
