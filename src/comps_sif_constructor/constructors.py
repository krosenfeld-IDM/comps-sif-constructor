"""
Functions to create and update simulation sweeps on COMPS
"""

import numpy as np
import pyDOE3 as pyDOE


def create_sweep(sweep_params: dict):
    """
    Create a full factorial design of the simulation sweep

    Args:
        sweep_params (dict): dictionary of parameters and their values
    """

    # use pyDOE to create the full factorial design (indices)
    inds = pyDOE.fullfact([len(sweep_params[k]) for k in sweep_params])

    # grab the samples values from the design (values)
    param_dict = dict()
    for ik, (k, v) in enumerate(sweep_params.items()):
        param_dict[k] = [v[int(i)] for i in inds[:, ik]]

    # number of samples in the full factorial design
    nsim = len(param_dict[k])

    return nsim, param_dict


def update_parameter_callback(simulation, **kwargs):
    """
    Update parameters of the simulation task

    Args:
        simulation (Simulation): simulation object
        **kwargs: keyword arguments of parameters to update
    """
    for k,v in kwargs.items():
        simulation.task.set_parameter(k, v)
    return kwargs