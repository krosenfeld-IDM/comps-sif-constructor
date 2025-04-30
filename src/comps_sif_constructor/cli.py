"""
CLI interface for comps-sif-constructor package.
"""

import click
import json
import sys
import traceback
from pathlib import Path

from comps_sif_constructor.launch import CompsExperiment
from idmtools.core.platform_factory import Platform
from idmtools_platform_comps.utils.singularity_build import SingularityBuildWorkItem
from idmtools.assets.file_list import FileList


def create_sif_func(definition_file, output_id, image_name, work_item_name, requirements):
    """Function that creates a Singularity image file on COMPS."""
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


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Command line interface for comps-sif-constructor."""
    if ctx.invoked_subcommand is None:
        pass


@cli.command('create')
@click.option("--definition_file", "-d", type=str, help="Path to the Singularity definition file", default="apptainer.def")
@click.option("--output_id", "-o", type=str, help="(optional) Name out Asset id file", default="sif.id")
@click.option("--image_name", "-i", type=str, help="(optional) Name of the Singularity image file", default="default.sif")
@click.option("--work_item_name", "-w", type=str, help="(optional) Name of the work item", default="Singularity Build")
@click.option("--requirements", "-r", type=str, help="(optional) Path to the requirements file", default=None)
def create_sif(definition_file, output_id, image_name, work_item_name, requirements):
    """Create a Singularity image file on COMPS."""
    create_sif_func(definition_file, output_id, image_name, work_item_name, requirements)


@cli.command('launch')
@click.option("--name", "-n", type=str, help="Name of the experiment", default="python")
@click.option("--threads", "-t", type=int, help="Number of threads to use", default=1)
@click.option("--priority", "-p", type=str, help="Priority level for the experiment", 
              default="AboveNormal")
@click.option("--node-group", "-g", type=str, help="Node group to use", default="idm_48cores")
@click.option("--file", "-f", type=click.Path(exists=True), help="Path to the trials.jsonl file", required=True)
@click.option("--sif-filename", "-s", type=str, help="Name of the singularity image file", default="default.sif")
@click.option("--sif-id-file", "-i", type=str, help="Path to the asset ID file", default="sif.id")
def launch(name, threads, priority, node_group, file, sif_filename, sif_id_file):
    """Launch a COMPS experiment with the specified parameters."""
    experiment = CompsExperiment(
        name=name,
        num_threads=threads,
        priority=priority,
        node_group=node_group,
        sif_filename=sif_filename,
        sif_id_file=sif_id_file
    )
    
    # Plan the experiment with the file
    experiment.plan(file_path=file)
    
    # Deploy the experiment
    return experiment.deploy()


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main() 