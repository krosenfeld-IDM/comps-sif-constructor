"""
CLI interface for comps-sif-constructor package.
"""
import os
import click

from .create_auth_tokens import StaticCredentialPrompt
from .launch import launch
from .gather import gather
from .create_sif import create_sif
from . import defaults

from COMPS import Client


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Command line interface for comps-sif-constructor."""
    if ctx.invoked_subcommand is None:
        pass


@cli.command('create')
@click.option("--definition_file", "-d", type=str, help="Path to the Singularity definition file (default: apptainer.def)", default="apptainer.def")
@click.option("--output_id", "-o", type=str, help="Name out Asset id file (default: sif.id)", default=defaults.SIF_ID_FILE)
@click.option("--work_item_name", "-w", type=str, help="Name of the work item (default: Singularity Build)", default=defaults.WORK_ITEM_NAME)
@click.option("--requirements", "-r", type=str, help="Path to the requirements file", default=None)
def create_sif_cli(definition_file, output_id, work_item_name, requirements):
    """Create a Singularity image file on COMPS."""
    create_sif(definition_file=definition_file, output_id=output_id, work_item_name=work_item_name, requirements=requirements)


@cli.command('launch')
@click.option("--name", "-n", type=str, help="Name of the experiment", default="comps-sif-constructor experiment")
@click.option("--file", "-f", type=click.Path(exists=True), help="Path to the trials.jsonl file (REQUIRED)", required=True)
@click.option("--threads", "-t", type=int, help="Number of threads to use", default=1)
@click.option("--priority", "-p", type=str, help="Priority level for the experiment", 
              default="AboveNormal")
@click.option("--node-group", "-g", type=str, help="Node group to use", default="idm_48cores")
@click.option("--sif-id-file", "-i", type=str, help="Path to the asset ID file (default: sif.id)", default=defaults.SIF_ID_FILE)
@click.option("--experiment-id-file", "-o", type=str, help="Path to the output id file (default: experiment.id)", default=defaults.EXPERIMENT_ID_FILE)
def launch_cli(name, threads, priority, node_group, file, sif_id_file, experiment_id_file):
    """Launch a COMPS experiment with the specified parameters."""
    launch(name=name, threads=threads, priority=priority, node_group=node_group, file=file, sif_id_file=sif_id_file, experiment_id_file=experiment_id_file)


@cli.command('gather')
@click.option("--experiment-id", "-e", type=str, help="Experiment id", default=defaults.EXPERIMENT_ID_FILE)
@click.option("--output", "-o", type=str, help="Output file (default: data_brick.json)", default=defaults.OUTPUT_FILE)
def gather_cli(experiment_id: str, output: str):
    """Gather data from a COMPS experiment."""
    return gather(experiment_id, output)


@cli.command('login')
@click.option("--comps_url", type=str, default='https://comps.idmod.org', help='comps url')
@click.option("--username", "-u", type=str, help='Username')
@click.option("--password", "-p", type=str, help='Password (use single quotes to avoid shell issues)')
def login(comps_url, username, password):
    """Login to COMPS with credentials."""
    compshost = comps_url
    username = username or os.getenv('COMPS_USERNAME')
    password = password or os.getenv('COMPS_PASSWORD')
    Client.login(compshost, StaticCredentialPrompt(comps_url=comps_url, 
                                                    username=username,
                                                    password=password))
    print("Login successful")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main() 