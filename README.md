# comps-sif-constructor
Create SIF images for COMPS

## Usage

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
