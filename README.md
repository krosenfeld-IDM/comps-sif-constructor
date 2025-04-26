# comps-sif-constructor
Create SIF images for COMPS

To use (with [uv](https://docs.astral.sh/uv/getting-started/installation/)):
```bash
uvx comps_sif_constructor lolcow.def
```

This will launch the image creation on COMPS and leave behind a `sif.id` for the jobs that need the image.

## Usage


```bash
comps_sif_constructor -h
usage: comps_sif_constructor [-h] [--definition_file DEFINITION_FILE] [--output_id OUTPUT_ID] [--image_name IMAGE_NAME] [--work_item_name WORK_ITEM_NAME] [--requirements REQUIREMENTS]

options:
  -h, --help            show this help message and exit
  --definition_file DEFINITION_FILE, -d DEFINITION_FILE
                        Path to the Singularity definition file
  --output_id OUTPUT_ID, -o OUTPUT_ID
                        Name out Asset id file
  --image_name IMAGE_NAME, -i IMAGE_NAME
                        Name of the Singularity image file
  --work_item_name WORK_ITEM_NAME, -w WORK_ITEM_NAME
                        Name of the work item
  --requirements REQUIREMENTS, -r REQUIREMENTS
                        Path to the requirements file
```

To create a Singularity image from a definition file:

```bash
python -m comps_sif_constructor.create_sif \
  -d <path_to_definition_file> \
  -o <output_id> \
  -i <image_name> \
  -w <work_item_name> \
  [-r <requirements_file>]
```

Or using the console script:

```bash
comps_sif_constructor \
  -d <path_to_definition_file> \
  -o <output_id> \
  -i <image_name> \
  -w <work_item_name> \
  [-r <requirements_file>]
```


