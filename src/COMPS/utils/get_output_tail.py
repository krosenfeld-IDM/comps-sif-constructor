import sys
import logging

from COMPS import Client
from COMPS.Data import QueryCriteria, AssetManager

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'tail' ],
    'help': 'Get the output tail from a simulation or workItem',
    'description': 'This utility displays the last chunk of output for a simulation or workItem.  By default, ' +
                   'it will show the last 1024 bytes of both stdout.txt and stderr.txt.',
    'epilog': '''examples:
  %(prog)s WorkItem 11111111-2222-3333-4444-000000000000
  %(prog)s Simulation latest status.txt -b 200
'''
}

def fill_parser(p):
    p.add_argument('entity_type', choices=_valid_entity_types, type=lambda arg: {x.lower(): x for x in _valid_entity_types}[arg.lower()],
                                help='Type of the entity to retrieve status for (must be one of Simulation or WorkItem)')
    p.add_argument('entity_id', help='Id of the entity to retrieve status for; can pass \'latest\' to get the latest of that entity type')
    p.add_argument('filename', default='stdout.txt,stderr.txt', nargs='?', help='Name(s) of the file(s) to retrieve the end of.  This can be a comma-delimited list, or an actual (python) list if calling from code (default is stdout.txt and stderr.txt)')
    p.add_argument('--bytes', '-b', type=int, default=1024, help='The number of bytes from the end of the output file to display (default=1024)')

##########################

_valid_entity_types = ['Simulation', 'WorkItem']

def get_tail(entity_type, entity_id, files_to_get, bytes=1024):
    if not isinstance(files_to_get, list):
        files_to_get = [ files_to_get ]

    entity_cls = getattr(sys.modules['COMPS.Data'], entity_type)
    entity_state_cls = getattr(sys.modules[f'COMPS.Data.{entity_type}'], f'{entity_type}State')

    if entity_id == 'latest':
        entity = entity_cls.get(query_criteria=QueryCriteria().select(['id','state'])
                                                                .where(f'owner={Client.auth_manager().username}')
                                                                .orderby('date_created desc')
                                                                .count(1))[0]
    else:
        entity = entity_cls.get(entity_id, QueryCriteria().select(['id','state']))

    logger.info(f'{entity_type} {entity.id}')

    if entity.state.value < entity_state_cls.Running.value:
        print('Can\'t retrieve output tail; entity has not started running yet!')
        return

    ofmd = entity.retrieve_output_file_info(files_to_get)

    for md in ofmd:
        logger.info('')
        logger.info(f'{"/".join([md.path_from_root, md.friendly_name])} :')

        retrieved_bytes = min(md.length, bytes + 3)
        barr_out = AssetManager.retrieve_partial_output_file_from_info(md, -1 * retrieved_bytes)

        decoded = False
        decode_bytes = retrieved_bytes
        while not decoded and decode_bytes >= max(0, retrieved_bytes - 3):
            try:
                outstr = barr_out[-1*decode_bytes:].decode()
                decoded = True
            except UnicodeDecodeError:
                logger.debug('UnicodeDecodeError!  Probably grabbed a chunk in the middle of a multibyte character... trying again')
                decode_bytes = decode_bytes - 1

        if not decoded:
            logger.error('Unable to decode output stream!')
            continue

        if '\r\n' in outstr:
            lines = outstr.split('\r\n')
        else:
            outstr = outstr.replace('\r','\n')
            lines = outstr.split('\n')

        for line in lines:
            logger.info('  >>  {0}'.format(line))

    return


def main(args):
    Client.login(args.comps_server)
    get_tail(args.entity_type, args.entity_id, args.filename.split(','), args.bytes)