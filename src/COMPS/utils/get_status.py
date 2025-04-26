import sys
import time
import logging

from COMPS import Client
from COMPS.Data import QueryCriteria

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'status' ],
    'help': 'Get the status of a simulation, experiment, or workitem',
    'description': 'This utility gets the status of a simulation, experiment, or workitem, outputting the current ' +
                   'state(s) for that entity.',
    'epilog': '''examples:
  %(prog)s WorkItem 11111111-2222-3333-4444-000000000000
  %(prog)s Experiment latest -r 60
'''
}

def fill_parser(p):
    p.add_argument('entity_type', choices=_valid_entity_types, type=lambda arg: {x.lower(): x for x in _valid_entity_types}[arg.lower()],
                                help='Type of the entity to retrieve status for (must be one of Simulation, Experiment, or WorkItem)')
    p.add_argument('entity_id', help='Id of the entity to retrieve status for; can pass \'latest\' to get the latest of that entity type')
    p.add_argument('--repeat', '-r', type=int, nargs='?', const=15, default=0, help='Repeat the status query until the entity is in a terminal state.  Optional REPEAT parameter controls seconds between queries (default=15)')
    p.add_argument('--quiet', '-q', action='store_true', help='Suppress showing of status output until/unless entity is complete')

##########################

_valid_entity_types = ['Simulation', 'Experiment', 'WorkItem']
_terminal_states = [ 'Succeeded', 'Failed', 'Canceled' ]

def get_status(entity_type, entity_id, repeat=15, quiet=False):
    terminal = False
    entity_cls = getattr(sys.modules['COMPS.Data'], entity_type)

    if entity_id == 'latest':
        entity_id = entity_cls.get(query_criteria=QueryCriteria().select(['id'])
                                                                .where(f'owner={Client.auth_manager().username}')
                                                                .orderby('date_created desc')
                                                                .count(1))[0].id

    logger.info(f'{entity_type} {entity_id}')

    while not terminal:
        if entity_type == 'Experiment':
            entities = entity_cls.get(entity_id).get_simulations(QueryCriteria().select(['id','state']))
        else:
            entities = [ entity_cls.get(entity_id, QueryCriteria().select(['id','state'])) ]

        states = [e.state.name for e in entities]
        terminal = repeat == 0 or all(s in _terminal_states for s in states)

        if terminal or not quiet:
            if len(states) > 1:
                state_cnt = { x : states.count(x) for x in set(states) }
                logger.info(', '.join([f'{s}: {state_cnt[s]}' for s in state_cnt]))
            else:
                logger.info(states[0])

        if not terminal:
            time.sleep(repeat)
    return


def main(args):
    Client.login(args.comps_server)
    get_status(args.entity_type, args.entity_id, args.repeat, args.quiet)