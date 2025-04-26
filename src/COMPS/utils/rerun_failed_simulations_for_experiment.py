import logging
from functools import partial
from multiprocessing import Pool

from COMPS import Client
from COMPS.Data import Experiment, Simulation, QueryCriteria
from COMPS.Data.Simulation import SimulationState

from COMPS.utils.clone_simulation import clone_simulation

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'rerunsims' ],
    'help': 'Rerun failed simulations for an experiment',
    'description': 'This utility creates duplicates of failed simulations in an experiment and reruns them.  By ' +
                   'default, failed simulations are considered to be those that are in state \'Failed\', but if ' +
                   'calling from script, another predicate can be provided (for example, to detect expected output ' +
                   'files that are missing, etc).  If the user running the utility is the owner of the original ' +
                   'experiment, the newly-created simulations will be placed in the original experiment, otherwise' +
                   'a new experiment will be created to hold the new simulations.',
    'epilog': '''examples:
  %(prog)s 11111111-2222-3333-4444-000000000000
  %(prog)s 11111111-2222-3333-4444-000000000000 --createonly
'''
}

def fill_parser(p):
    p.add_argument('experiment_id', help='Id of the experiment containing the failed simulations to rerun')
    p.add_argument('--createonly', '-co', action='store_true', help='Only recreate the failed simulations but suppress running (default is to automatically run)')
    p.add_argument('--deleteold', '-del', action='store_true', help='Delete the failed simulations after the new ones have been created (default is to not delete them).  ' +
                                                                    'If the sims are not deleted, they will be tagged for easier identification for manual deletion later')

##########################

def is_failed_sim_simple(hoststring, sim):
    return sim.state == SimulationState.Failed

# If you want to use a custom predicate to determine what is considered a 'failed' simulation, you can define
# a function something like this and pass it in when calling this utility:
#
# def is_failed_sim(hoststring, sim):
#     if sim.state == SimulationState.Failed:
#         return True
#
#     # Python pools get run in subprocesses (not threads), hence we're not logged in from that process and have to
#     # do so again.  But these subprocesses also appear to get reused, so after the first time we login from the
#     # subprocess, we actually *will* already be logged in, so we'll get a bunch of "skipping login" messages.
#     # To avoid this spam, let's suppress logger messages from COMPS.Client temporarily.
#     from COMPS.Client import logger as client_logger
#
#     client_logger.disabled = True
#     Client.login(hoststring)
#     client_logger.disabled = False
#
#     fi = sim.retrieve_output_file_info(None)
#
#     if not any(filter(lambda x: x.path_from_root == 'output' and x.friendly_name.startswith('RequiredReport_'), fi)):
#         return True
#
#     return False

##########################

def rerun_sims(expid, createonly=False, deleteold=False, predicate=is_failed_sim_simple):
    exp = Experiment.get(expid)

    sims = exp.get_simulations(query_criteria=QueryCriteria().select_children(['files','tags','configuration']))

    # Depending on what the user does in the predicate and the size of the experiment, this step can
    # take quite a while, so do it in a Pool to speed things up.  This may sometimes be overkill (and
    # slower because of the overhead of cross-process stuff), but that's going to be in the very quick
    # scenarios anyway, and adding more logic seems like unnecessary complexity.
    with Pool() as p:
        results = p.map(partial(predicate, Client.auth_manager().hoststring), sims)

    # Not sure why this is needed, but it seems to flush out some weirdness between multiprocessing + logging
    # that is causing logging to file to be goofed up. *sigh*
    logger.debug('')

    sims_to_rerun = [ sims[i] for i in filter(lambda x: results[x] == True, range(len(results))) ]

    if len(sims_to_rerun) == 0:
        logger.info('No sims found to rerun')
        return

    logger.info(f'Found {len(sims_to_rerun)} sims to rerun')

    new_expid = None

    logger.info(f'Recreating simulations')

    for sim in sims_to_rerun:
        new_sim = clone_simulation(sim, new_expid, False)
        new_expid = new_sim.experiment_id

    if exp.id != new_expid:
        logger.warning('Current user is not the owner of the original experiment')
        logger.warning(f'Created new experiment to hold the new simulations: {new_expid}')
        exp = Experiment.get(new_expid)

    Simulation.save_all()
    logger.info('')

    if not createonly:
        logger.info('Recommissioning simulations')
        exp.commission()

    if deleteold:
        logger.info('Deleting old simulations')
        for sim in sims_to_rerun:
            sim.delete()
    else:
        if str(expid) == str(new_expid):
            logger.info('Tagging old simulations with \'ClonedToRerun\' tag for easier deletion later')
            for sim in sims_to_rerun:
                sim.merge_tags({'ClonedToRerun': None})

    logger.info('Done')


def main(args):
    Client.login(args.comps_server)
    rerun_sims(args.experiment_id, args.createonly, args.deleteold)
