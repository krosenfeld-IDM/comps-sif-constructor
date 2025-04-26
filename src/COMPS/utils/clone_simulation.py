import copy
import logging

from COMPS import Client
from COMPS.Data import Simulation, SimulationFile, QueryCriteria, Configuration, Experiment

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'clonesim' ],
    'help': 'Clone an existing simulation',
    'description': 'This utility clones an existing simulation, including all tags, files, etc (but not state).',
    'epilog': '''examples:
  %(prog)s 11111111-2222-3333-4444-000000000000
  %(prog)s 11111111-2222-3333-4444-000000000000 --experiment_id 55555555-6666-7777-8888-999999999999
'''
}

def fill_parser(p):
    p.add_argument('simulation_id', help='Id of the simulation to clone')
    p.add_argument('--experiment_id', '-eid', help='Id of the experiment to put the new simulation in (the default if the current user is the owner ' +
                                                   'of the original experiment is to use that experiment, otherwise a new experiment will be created)')

##########################

def clone_simulation(sim, expid=None, savesim=True):
    sim2 = Simulation(sim.name, description=sim.description)

    # If the user specifies an experiment, assume they know what they're doing and attempt to create the new simulation
    # in there.  If not, and if the current user is the owner of the original simulation, create the new simulation in
    # the same experiment as the original.  Otherwise, create a new experiment (since you can't put simulations in
    # someone else's experiment).

    if expid:
        sim2.experiment_id = expid
    elif sim.owner == Client.auth_manager().username:
        sim2.experiment_id = sim.experiment_id
    else:
        exp = Experiment('Dummy Experiment')
        exp.configuration = Experiment.get(sim.experiment_id, query_criteria=QueryCriteria().select_children(['configuration']) \
                                                                                            .add_extra_params({'coalesceConfig':True})).configuration
        exp.set_tags({'ClonedFromExperiment': str(sim.experiment_id)})
        exp.save()
        sim2.experiment_id = exp.id

    tags = copy.copy(sim.tags)
    tags['ClonedFromSimulation'] = str(sim.id)
    sim2.set_tags(tags)

    job = sim.hpc_jobs[-1] if sim.hpc_jobs else None
    cfg = sim.configuration if sim.configuration else job.configuration if job else None

    if cfg:
        sim2.configuration = Configuration(
            environment_name=cfg.environment_name,
            executable_path=cfg.executable_path,
            simulation_input_args=cfg.simulation_input_args,
            working_directory_root=cfg.working_directory_root,
            maximum_number_of_retries=cfg.maximum_number_of_retries,
            priority=cfg.priority,
            min_cores=cfg.min_cores,
            max_cores=cfg.max_cores,
            exclusive=cfg.exclusive,
            node_group_name=cfg.node_group_name,
            asset_collection_id=cfg.asset_collection_id)

    for f in sim.files or []:
        sf = SimulationFile(f.file_name, f.file_type, f.description, f.md5_checksum)
        sim2.add_file(sf)

    if savesim:
        sim2.save()
        logging.info(f'Created new sim: {sim2.id}')

    return sim2


def main(args):
    Client.login(args.comps_server)
    s = Simulation.get(args.simulation_id, query_criteria=QueryCriteria().select_children(['files', 'tags', 'configuration']))
    clone_simulation(s, args.experiment_id)
