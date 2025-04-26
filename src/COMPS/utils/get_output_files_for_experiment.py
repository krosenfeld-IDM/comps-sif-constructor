import os
import logging
from functools import partial
from multiprocessing import Pool
from requests.exceptions import HTTPError

from COMPS import Client
from COMPS.Data import Experiment, QueryCriteria
from COMPS.Data.Simulation import SimulationState

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'getexpout' ],
    'help': 'Download output files from each simulation in an experiment',
    'description': 'This utility downloads one or more output files from each simulation in an experiment.  By ' +
                   'default, files are written relative to the current directory, in the hierarchy:' + os.linesep +
                   '    ./<exp-id>/<sim-id>/<filename>' + os.linesep +
                   'but if calling from script, a custom function can be provided to control location and ' +
                   'name of the files written.',
    'epilog': '''examples:
  %(prog)s 11111111-2222-3333-4444-000000000000 insetchart.json
  %(prog)s 11111111-2222-3333-4444-000000000000 stdout.txt,stderr.txt
'''
}

def fill_parser(p):
    p.add_argument('experiment_id', help='Id of the experiment containing the simulations to download files from')
    p.add_argument('filename', help='Name(s) of the file(s) to download from each simulation.  This can be a comma-delimited list, or an actual (python) list if calling from code')
    p.add_argument('--overwrite', '-ow', action='store_true', help='Overwrite local files if they already exist (default is to skip if a local file with the same subdir/name exists)')
    p.add_argument('--casesensitive', '-cs', action='store_true', help='Make filename comparisons case-sensitive (default is case-insensitive, i.e. ignoring case)')

##########################

# The default path builder
def path_builder_simple(sim, filename):
    return os.path.join(str(sim.experiment_id), str(sim.id), filename)

# A sample, custom path builder that puts all the files in a single directory but modifies the output file names
# to avoid collissions and distinguish between the output for the simulations.
def path_builder_single_dir(sim, filename):
    sp = os.path.splitext(filename)
    return os.path.join(str(sim.experiment_id), f'{sp[0]}_{str(sim.id)}{sp[1]}')

##########################

def get_files( experiment_id, files_to_get, overwrite=False, casesensitive=False, output_path_builder=path_builder_simple ):
    if not isinstance(files_to_get, list):
        files_to_get = [ files_to_get ]

    files_to_get_int = files_to_get if casesensitive else [ f.lower() for f in files_to_get ]

    exp = Experiment.get(experiment_id)
    logger.info(f'Found experiment {exp.id}')

    sims = exp.get_simulations()
    logger.info(f'{len(sims)} child simulations found')

    # sims that haven't finished Provisioning yet don't have an hpc-job / working-directory, so filter
    # to only the potentially valid set of sims
    valid_sims = [ s for s in sims if s.state.value >= SimulationState.Commissioned.value ]

    if len(valid_sims) < len(sims):
        logger.warning(f'!!! WARNING !!!  Sims cannot have output downloaded prior to completing commissioning')
        if len(valid_sims) == 0:
            logger.warning(f'No valid simulations to attempt file download for')
        else:
            logger.warning(f'Only attempting file download for {len(valid_sims)} simulations')

    with Pool() as p:
        results = p.map(partial(_get_files_internal, Client.auth_manager().hoststring, files_to_get_int, overwrite, casesensitive, output_path_builder), valid_sims)

    hit_fileexists = any([r[0] for r in results])
    missing_files = any([r[1] for r in results])

    if missing_files:
        logger.warning('')
        logger.warning(f'Couldn\'t find files matching requested for some sims (possible typo, casing issue, or requested an input-asset?)')

    if hit_fileexists:
        logger.warning('')
        logger.warning('Skipped downloading of some files because they already exist locally.  Rerun using the overwrite argument if you want these overwritten instead')


def _get_files_internal(hoststring, files_to_get_int, overwrite, casesensitive, output_path_builder, sim):
    # Python pools get run in subprocesses (not threads), hence we're not logged in from that process and have to
    # do so again.  But these subprocesses also appear to get reused, so after the first time we login from the
    # subprocess, we actually *will* already be logged in, so we'll get a bunch of "skipping login" messages.
    # To avoid this spam, let's suppress logger messages from COMPS.Client temporarily.
    from COMPS.Client import logger as client_logger
    client_logger.disabled = True
    Client.login(hoststring)
    client_logger.disabled = False

    try:
        so = sim.retrieve_output_file_info(None)
    except HTTPError as e:
        sim.refresh(QueryCriteria().select_children(['hpc_jobs']))
        if not sim.hpc_jobs or len(sim.hpc_jobs) == 0:
            logger.warning(f'No hpc-job found for simulation {sim.id}')
            return (False, True)
        raise e

    logger.debug(f'sim {sim.id} - {len(so)} output files found')

    found_file_num = 0

    hit_fileexists = False
    missing_files = False

    for ofmd in so:
        fn_comp = ofmd.friendly_name if casesensitive else ofmd.friendly_name.lower()

        if fn_comp in files_to_get_int:
            found_file_num += 1

            filepath = output_path_builder(sim, ofmd.friendly_name)

            pn = os.path.dirname(filepath)
            if not os.path.exists(pn):
                os.makedirs(pn, exist_ok=True)

            logger.info(filepath)
            oba = sim.retrieve_output_files_from_info([ofmd])
            try:
                with open(filepath, 'wb' if overwrite else 'xb') as outfile:
                    outfile.write(oba[0])
            except FileExistsError as e:
                logger.error(f'Output file already exists at {filepath}.  Skipping...')
                logger.debug(e, exc_info=True)
                hit_fileexists = True

    # if we didn't find enough matching files, spit out a message
    if found_file_num < len(files_to_get_int):
        logger.warning(f'Didn\'t find files to match all requested for sim {sim.id}')
        missing_files = True

    return (hit_fileexists, missing_files)


def main(args):
    Client.login(args.comps_server)
    get_files(args.experiment_id, args.filename.split(','), args.overwrite, args.casesensitive)
