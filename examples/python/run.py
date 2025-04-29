"""
https://github.com/gatesfoundation/GEOMED24/blob/main/calibration/calib_hartmann/run_service.py
"""
import os
import argparse

from comps_sif_constructor.launch import CompsExperiment

def use_list(experiment):
    content = [
        {'messages': 'Paris is the capital of France.'},
        {'messages': 'The Eiffel Tower is in Paris.'},
        {'messages': 'The Louvre is in Paris.'},
        {'messages': 'The Arc de Triomphe is in Paris.'},
        {'messages': 'The Louvre is in Paris.'}
    ]
    experiment.plan(content=content)

def use_file(experiment):
    experiment.plan(file_path="trials_.jsonl")

if __name__ == "__main__":
    # Change directory to the location of this file
    os.chdir(os.path.dirname(__file__))
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run experiment with list or file input.')
    parser.add_argument('--use-file', type=bool, default=True, help='Use file input instead of list')
    args = parser.parse_args()

    # Create and deploy the experiment
    experiment = CompsExperiment(name='python', num_threads=1, priority="AboveNormal", num_trials=5)

    if args.use_file:
        use_file(experiment)
    else:
        use_list(experiment)

    experiment.deploy()
