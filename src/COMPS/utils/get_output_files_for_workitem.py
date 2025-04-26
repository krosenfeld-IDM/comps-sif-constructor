import os
import logging

from COMPS import Client
from COMPS.Data import WorkItem

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'getwiout' ],
    'help': 'Download output files from a workitem',
    'description': 'This utility downloads one or more output files from a workitem.  By ' +
                   'default, files are written relative to the current directory, in the hierarchy:' + os.linesep +
                   '    ./<workitem-id>/<filename>' + os.linesep +
                   'but if calling from script, a custom function can be provided to control location and ' +
                   'name of the files written.',
    'epilog': '''examples:
  %(prog)s 11111111-2222-3333-4444-000000000000 schema.json
  %(prog)s 11111111-2222-3333-4444-000000000000 stdout.txt,stderr.txt
'''
}

def fill_parser(p):
    p.add_argument('workitem_id', help='Id of the workitem to download files from')
    p.add_argument('filename', help='Name(s) of the file(s) to download from the workitem.  This can be a comma-delimited list, or an actual (python) list if calling from code')
    p.add_argument('--overwrite', '-ow', action='store_true', help='Overwrite local files if they already exist (default is to skip if a local file with the same subdir/name exists)')
    p.add_argument('--casesensitive', '-cs', action='store_true', help='Make filename comparisons case-sensitive (default is case-insensitive, i.e. ignoring case)')

##########################

# The default path builder
def path_builder_simple(wi, filename):
    return os.path.join(str(wi.id), filename)

##########################

def get_files( workitem_id, files_to_get, overwrite=False, casesensitive=False, output_path_builder=path_builder_simple ):
    if not isinstance(files_to_get, list):
        files_to_get = [ files_to_get ]

    files_to_get_int = files_to_get if casesensitive else [ f.lower() for f in files_to_get ]

    wi = WorkItem.get(workitem_id)
    logger.info(f'Found workitem {wi.id}')

    hit_fileexists = False

    wo = wi.retrieve_output_file_info(None)
    logger.debug(f'wi {wi.id} - {len(wo)} output files found')

    found_file_num = 0

    for ofmd in wo:
        fn_comp = ofmd.friendly_name if casesensitive else ofmd.friendly_name.lower()

        if fn_comp in files_to_get_int:
            found_file_num += 1

            filepath = output_path_builder(wi, ofmd.friendly_name)

            pn = os.path.dirname(filepath)
            if not os.path.exists(pn):
                os.makedirs(pn, exist_ok=True)

            logger.info(filepath)
            oba = wi.retrieve_output_files_from_info([ofmd])
            try:
                with open(filepath, 'wb' if overwrite else 'xb') as outfile:
                    outfile.write(oba[0])
            except FileExistsError as e:
                logger.error(f'Output file already exists at {filepath}.  Skipping...')
                logger.debug(e, exc_info=True)
                hit_fileexists = True

    # if we didn't find enough matching files, spit out a message
    if found_file_num < len(files_to_get_int):
        logger.warning(f'Couldn\'t find all files matching request (possible typo, casing issue, or requested an input-asset?)')

    if hit_fileexists:
        logger.warning('Skipped downloading of some files because they already exist locally.  Rerun using \'--overwrite\' if you want these overwritten instead')


def main(args):
    Client.login(args.comps_server)
    get_files(args.workitem_id, args.filename.split(','), args.overwrite, args.casesensitive)
