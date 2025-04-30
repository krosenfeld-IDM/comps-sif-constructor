# comps-sif-constructor
Create SIF images for COMPS

To use (with [uv](https://docs.astral.sh/uv/getting-started/installation/)):
```bash
uvx comps_sif_constructor create -d lolcow.def
```

This will launch the image creation on COMPS and leave behind a `sif.id` for the jobs that need the image.

## Usage

```bash
comps_sif_constructor --help
```

The CLI has two main commands: `create` and `launch`.

### Create SIF Image

Create a Apptainer/Singularity image file on COMPS with `create`:

```bash
comps_sif_constructor create --help
usage: comps_sif_constructor create [--help] [--definition_file DEFINITION_FILE] [--output_id OUTPUT_ID] 
                                    [--image_name IMAGE_NAME] [--work_item_name WORK_ITEM_NAME] 
                                    [--requirements REQUIREMENTS]

options:
  --help                show this help message and exit
  --definition_file DEFINITION_FILE, -d DEFINITION_FILE
                        Path to the Singularity definition file
  --output_id OUTPUT_ID, -o OUTPUT_ID
                        (optional) Name out Asset id file
  --image_name IMAGE_NAME, -i IMAGE_NAME
                        (optional) Name of the Singularity image file
  --work_item_name WORK_ITEM_NAME, -w WORK_ITEM_NAME
                        (optional) Name of the work item
  --requirements REQUIREMENTS, -r REQUIREMENTS
                        (optional) Path to the requirements file
```

Example:
```bash
comps_sif_constructor create \
  -d <path_to_definition_file> \
  -o <output_id> \
  -i <image_name> \
  -w <work_item_name> \
  [-r <requirements_file>]
```

### Launch COMPS Experiment

Launch a COMPS experiment with specified parameters:

```bash
comps_sif_constructor launch -h
usage: comps_sif_constructor launch [--help] [--name NAME] [--threads THREADS] 
                                   [--priority PRIORITY] [--node-group NODE_GROUP] 
                                   --file FILE [--sif-filename SIF_FILENAME]
                                   [--sif-id-file SIF_ID_FILE]

options:
  --help                show this help message and exit
  --name NAME, -n NAME  Name of the experiment
  --threads THREADS, -t THREADS
                        Number of threads to use
  --priority PRIORITY, -p PRIORITY
                        Priority level for the experiment
  --node-group NODE_GROUP, -g NODE_GROUP
                        Node group to use
  --file FILE, -f FILE  Path to the trials.jsonl file
  --sif-filename SIF_FILENAME, -s SIF_FILENAME
                        Name of the singularity image file
  --sif-id-file SIF_ID_FILE, -i SIF_ID_FILE
                        Path to the asset ID file
```

Example:
```bash
comps_sif_constructor launch \
  -n "My Experiment" \
  -t 4 \
  -p AboveNormal \
  -g idm_48cores \
  -f trials.jsonl \
  -s custom_image.sif \
  -i custom_image.id
```

Launch expect a `run.sh` and `remote.py` to be colocated. You can also pass a `trials.jsonl`. See the `examples/` for more info.

## Resources
- Learn about [definition files](https://apptainer.org/docs/user/latest/definition_files.html#definition-files)

