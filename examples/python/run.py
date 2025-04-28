"""
https://github.com/gatesfoundation/GEOMED24/blob/main/calibration/calib_hartmann/run_service.py
"""
import os

from comps_sif_constructor.launch import CompsExperiment

if __name__ == "__main__":
    # Change directory to the location of this file
    os.chdir(os.path.dirname(__file__))

    # Create and deploy the experiment
    experiment = CompsExperiment(name='python', num_threads=1, priority="AboveNormal")
    experiment.deploy()
