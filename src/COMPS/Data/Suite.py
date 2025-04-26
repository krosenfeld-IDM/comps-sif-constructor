import json
from datetime import date, datetime
import logging
from enum import Enum
import uuid
import copy
from COMPS import Client
from COMPS.Data import Configuration, QueryCriteria, Experiment
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, parse_ISO8601_date, convert_if_string
from COMPS.Data.RelatableEntity import RelatableEntity
from COMPS.Data.TaggableEntity import TaggableEntity
from COMPS.Data.CommissionableEntity import CommissionableEntity

logger = logging.getLogger(__name__)

@json_entity()
class Suite(TaggableEntity, CommissionableEntity, RelatableEntity, SerializableEntity):
    """
    Represents a grouping of Experiments.

    Contains various basic properties accessible by getters (and, in some cases, +setters):

    * id
    * +name
    * +description
    * owner
    * date_created
    * last_modified

    Also contains "child objects" (which must be specifically requested for retrieval using the
    QueryCriteria.select_children() method of QueryCriteria):

    * tags
    * configuration
    """

    def __init__(self, name, description=None, configuration=None):
        if not name:
            raise RuntimeError('Suite has not been initialized properly; non-null name required.')

        self._id = None
        self._name = name
        self._description = description
        self._owner = Client.auth_manager().username
        self._date_created = None
        self._last_modified = None
        self._tags = None
        self._configuration = configuration

        self._is_dirty = None       # these will be set in _register_change() below
        self._is_config_dirty = None

        self._register_change(config_changed=(configuration is not None))

    @classmethod
    def __internal_factory__(cls, id=None, name=None, description=None, owner=None,
                             date_created=None, last_modified=None, tags=None, configuration=None):
        ste = cls.__new__(cls)

        ste._id = convert_if_string(id, uuid.UUID)
        ste._name = name
        ste._description = description
        ste._owner = owner
        ste._date_created = convert_if_string(date_created, parse_ISO8601_date)
        ste._last_modified = convert_if_string(last_modified, parse_ISO8601_date)
        ste._tags = tags

        if configuration:
            if isinstance(configuration, Configuration):
                ste._configuration = configuration
            else:
                config_json = Configuration.rest2py(configuration)
                ste._configuration = Configuration(**config_json)
        else:
            ste._configuration = None

        ste._is_dirty = False
        ste._is_config_dirty = False

        return ste

    @json_property()
    def id(self):
        return self._id

    @json_property()
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name
        self._register_change()

    @json_property()
    def description(self):
        return self._description

    @description.setter
    def description(self, description):
        self._description = description
        self._register_change()

    @json_property()
    def owner(self):
        return self._owner

    @json_property()
    def date_created(self):
        return self._date_created

    @json_property()
    def last_modified(self):
        return self._last_modified

    @json_property()
    def tags(self):
        return self._tags       # todo: immutable dict?

    @json_property()
    def configuration(self):
        return self._configuration

    @configuration.setter
    def configuration(self, configuration):
        self._configuration = configuration
        self._register_change(config_changed=True)

    ########################

    @classmethod
    def get(cls, id=None, query_criteria=None):
        """
        Retrieve one or more Suites.

        :param id: The id (str or UUID) of the Suite to retrieve
        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of Suites returned, as well as which properties and child-objects to \
        fill for the returned Suites
        :return: A Suite or list of Suites (depending on whether 'id' was specified) with \
        basic properties and child-objects assigned as specified by 'query_criteria'
        """
        if id and not isinstance(id, uuid.UUID):
            try:
                id = uuid.UUID(id)
            except ValueError:
                raise ValueError('Invalid id: {0}'.format(id))

        qc_params = query_criteria.to_param_dict(Suite) if query_criteria else {}

        path = '/Suites{0}'.format('/' + str(id) if id else '')
        resp = Client.get(path
                          , params = qc_params)

        json_resp = resp.json()

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('Suite Response:')
        #     logger.debug(json.dumps(json_resp, indent=4))

        if 'Suites' not in json_resp or \
                ( id is not None and len(json_resp['Suites']) != 1 ):
            logger.debug(json_resp)
            raise RuntimeError('Malformed Suites retrieve response!')

        stes = []

        for ste_json in json_resp['Suites']:
            ste_json = cls.rest2py(ste_json)

            # if logger.isEnabledFor(logging.DEBUG):
            #     logger.debug('Suite:')
            #     logger.debug(json.dumps(ste_json, indent=4))

            ste = Suite.__internal_factory__(**ste_json)
            stes.append(ste)

        if id is not None:
            return stes[0]
        else:
            return stes

    def refresh(self, query_criteria=None):
        """
        Update properties of an existing Suite from the server.

        :param query_criteria: A QueryCriteria object specifying which properties and child-objects \
        to refresh on the Suite
        """
        if not self._id:
            raise RuntimeError('Can\'t refresh a Suite that hasn\'t been saved!')

        ste = self.get(id=self.id, query_criteria=query_criteria)

        # if ste.id:                           self._id = ste.id
        if ste.name is not None:             self._name = ste.name
        if ste.description is not None:      self._description = ste.description
        if ste.owner is not None:            self._owner = ste.owner
        if ste.date_created is not None:     self._date_created = ste.date_created
        if ste.last_modified is not None:    self._last_modified = ste.last_modified

        if ste.tags is not None:             self._tags = ste.tags
        if ste.configuration is not None:    self._configuration = ste.configuration

    def get_experiments(self, query_criteria=None):
        """
        Retrieve Experiments contained in this Suite.

        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of Experiments returned, as well as which properties and child-objects to \
        fill for the returned Experiments
        :return: A list of Experiments with basic properties and child-objects assigned as specified \
        by 'query_criteria'
        """
        if not self._id:
            raise RuntimeError('Invalid call to get_experiments(); Suite hasn\'t been saved yet')

        qc = copy.copy(query_criteria) if query_criteria else QueryCriteria()
        qc = qc.where('suite_id={0}'.format(str(self._id)))

        return Experiment.get(query_criteria=qc)

    def save(self):
        """
        Save a single Suite.  If it's a new Suite, an id is automatically assigned.
        """
        if not self._is_dirty:
            logger.info('Suite has not been altered... no point in saving it!')
            return

        if not self._id:
            ste_to_save = self
        else:
            ste_to_save = self.__internal_factory__(id=self._id,
                                                    name=self._name,
                                                    description=self._description,
                                                    configuration=self._configuration if self._is_config_dirty else None)

        save_ste = SerializableEntity.convertToDict(ste_to_save, include_hidden_props=True)

        # indentval = 4 if logger.isEnabledFor(logging.DEBUG) else None

        json_str = json.dumps({'Suites': [ save_ste ] },
                              # indent=indentval,
                              default=lambda obj:
                                            obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                            else str(obj) if isinstance(obj, uuid.UUID)
                                            else obj.name if isinstance(obj, Enum)
                                            else obj)

        resp = Client.post('/Suites'
                           , data=json_str )

        json_resp = resp.json()

        if not self._id:
            self._id = uuid.UUID(json_resp['Ids'][0])

        self._is_dirty = False
        self._is_config_dirty = False

    def _register_change(self, config_changed=False):
        if not self._is_dirty:
            self._is_dirty = True

        if config_changed and not self._is_config_dirty:
            self._is_config_dirty = True
