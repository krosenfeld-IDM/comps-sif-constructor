"""
CLI interface for comps-sif-constructor package.
"""

import click
import json
from pathlib import Path
from comps_sif_constructor.launch import CompsExperiment


@click.group()
def cli():
    """Command line interface for comps-sif-constructor."""
    pass


@cli.command()
@click.option("--name", "-n", type=str, help="Name of the experiment", default="python")
@click.option("--threads", "-t", type=int, help="Number of threads to use", default=1)
@click.option("--priority", "-p", type=str, help="Priority level for the experiment", 
              default="AboveNormal")
@click.option("--node-group", "-g", type=str, help="Node group to use", default="idm_48cores")
@click.option("--file", "-f", type=click.Path(exists=True), help="Path to the trials.jsonl file", required=True)
def launch(name, threads, priority, node_group, file):
    """Launch a COMPS experiment with the specified parameters."""
    experiment = CompsExperiment(
        name=name,
        num_threads=threads,
        priority=priority,
        node_group=node_group
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