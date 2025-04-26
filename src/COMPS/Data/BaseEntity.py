from collections import namedtuple

EntityType = namedtuple('EntityType', ['name', 'article', 'has_state'])

entity_types = [ EntityType( 'Simulation',      'a',  True  ),
                 EntityType( 'Experiment',      'an', False ),
                 EntityType( 'Suite',           'a',  False ),
                 EntityType( 'WorkItem',        'a',  True  ),
                 EntityType( 'AssetCollection', 'an', False  ) ]

entity_type_map = {}

def get_entity_type(cls):
    if cls not in entity_type_map:
        matching_ets = list(filter(lambda et: et.name == cls.__name__, entity_types))
        if len(matching_ets) == 0:
            parent_entity_type = None
            for parent_cls in cls.__bases__:
                if parent_cls is not object:
                    parent_entity_type = get_entity_type(parent_cls)
            if parent_entity_type is None:
                raise RuntimeError('Unable to find EntityType \'{0}\' in map'.format(cls.__name__))
            matching_ets = [ parent_entity_type ]
        entity_type_map[cls] = matching_ets[0]
        return matching_ets[0]

    return entity_type_map[cls]
