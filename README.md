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

The CLI has four main commands: `create`, `launch`, `gather`, and `login`.

### Create SIF Image

Create a Apptainer/Singularity image file on COMPS with `create`:

```bash
comps_sif_constructor create --help
usage: comps_sif_constructor create [--help] [--definition_file DEFINITION_FILE] [--output_id OUTPUT_ID] 
                                    [--work_item_name WORK_ITEM_NAME] [--requirements REQUIREMENTS]

options:
  --help                show this help message and exit
  --definition_file DEFINITION_FILE, -d DEFINITION_FILE
                        Path to the Singularity definition file (default: apptainer.def)
  --output_id OUTPUT_ID, -o OUTPUT_ID
                        Name out Asset id file (default: sif.id)
  --work_item_name WORK_ITEM_NAME, -w WORK_ITEM_NAME
                        Name of the work item (default: Singularity Build)
  --requirements REQUIREMENTS, -r REQUIREMENTS
                        Path to the requirements file
```

Example:
```bash
comps_sif_constructor create \
  -d <path_to_definition_file> \
  -o <output_id> \
  -w <work_item_name> \
  [-r <requirements_file>]
```

### Launch COMPS Experiment

Launch a COMPS experiment with specified parameters:

```bash
comps_sif_constructor launch --help
usage: comps_sif_constructor launch [--help] [--name NAME] [--threads THREADS] 
                                   [--priority PRIORITY] [--node-group NODE_GROUP] 
                                   --file FILE [--sif-id-file SIF_ID_FILE]
                                   [--experiment-id-file EXPERIMENT_ID_FILE]

options:
  --help                show this help message and exit
  --name NAME, -n NAME  Name of the experiment (default: comps-sif-constructor experiment)
  --threads THREADS, -t THREADS
                        Number of threads to use (default: 1)
  --priority PRIORITY, -p PRIORITY
                        Priority level for the experiment (default: AboveNormal)
  --node-group NODE_GROUP, -g NODE_GROUP
                        Node group to use (default: idm_48cores)
  --file FILE, -f FILE  Path to the trials.jsonl file (REQUIRED)
  --sif-id-file SIF_ID_FILE, -i SIF_ID_FILE
                        Path to the asset ID file (default: sif.id)
  --experiment-id-file EXPERIMENT_ID_FILE, -o EXPERIMENT_ID_FILE
                        Path to the output id file (default: experiment.id)
```

Example:
```bash
comps_sif_constructor launch \
  -n "My Experiment" \
  -t 4 \
  -p AboveNormal \
  -g idm_48cores \
  -f trials.jsonl \
  -i sif.id \
  -o experiment.id
```

### Gather Experiment Data

Gather data from a COMPS experiment:

```bash
comps_sif_constructor gather --help
usage: comps_sif_constructor gather [--help] [--experiment-id EXPERIMENT_ID] [--output OUTPUT]

options:
  --help                show this help message and exit
  --experiment-id EXPERIMENT_ID, -e EXPERIMENT_ID
                        Experiment id (default: experiment.id)
  --output OUTPUT, -o OUTPUT
                        Output file (default: data_brick.json)
```

Example:
```bash
comps_sif_constructor gather \
  -e experiment.id \
  -o data_brick.json
```

### Login
Save your COMPS credentials using the login command:

```bash
comps_sif_constructor login --help
usage: comps_sif_constructor login [--help] [--comps_url COMPS_URL] [--username USERNAME] [--password PASSWORD]

options:
  --help                show this help message and exit
  --comps_url COMPS_URL
                        COMPS URL (default: https://comps.idmod.org)
  --username USERNAME, -u USERNAME
                        Username (can also use COMPS_USERNAME environment variable)
  --password PASSWORD, -p PASSWORD
                        Password (can also use COMPS_PASSWORD environment variable)
```

Example:
```bash
comps_sif_constructor login \
  -u your_username \
  -p 'your_password'
```

You can also set `COMPS_USERNAME` and `COMPS_PASSWORD` as environment variables to avoid entering credentials each time.

## Resources
- Learn about [definition files](https://apptainer.org/docs/user/latest/definition_files.html#definition-files)

