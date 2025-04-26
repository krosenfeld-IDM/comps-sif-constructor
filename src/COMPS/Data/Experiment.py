import json
from datetime import date, datetime
import logging
from enum import Enum
import uuid
import copy
from COMPS import Client
from COMPS.Data import Configuration, QueryCriteria, Simulation
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, parse_ISO8601_date, convert_if_string
from COMPS.Data.RelatableEntity import RelatableEntity
from COMPS.Data.TaggableEntity import TaggableEntity
from COMPS.Data.CommissionableEntity import CommissionableEntity

logger = logging.getLogger(__name__)

@json_entity()
class Experiment(TaggableEntity, CommissionableEntity, RelatableEntity, SerializableEntity):
    """
    Represents a grouping of Simulations.

    Contains various basic properties accessible by getters (and, in some cases, +setters):

    * id
    * +suite_id
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

    def __init__(self, name, suite_id=None, description=None, configuration=None):
        if not name:
            raise RuntimeError('Experiment has not been initialized properly; non-null name required.')

        self._id = None
        self._name = name
        self._suite_id = suite_id
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
    def __internal_factory__(cls, id=None, name=None, suite_id=None, description=None, owner=None,
                             date_created=None, last_modified=None, tags=None, configuration=None):
        exp = cls.__new__(cls)

        exp._id = convert_if_string(id, uuid.UUID)
        exp._name = name
        exp._suite_id = convert_if_string(suite_id, uuid.UUID)
        exp._description = description
        exp._owner = owner
        exp._date_created = convert_if_string(date_created, parse_ISO8601_date)
        exp._last_modified = convert_if_string(last_modified, parse_ISO8601_date)
        exp._tags = tags

        if configuration:
            if isinstance(configuration, Configuration):
                exp._configuration = configuration
            else:
                config_json = Configuration.rest2py(configuration)
                exp._configuration = Configuration(**config_json)
        else:
            exp._configuration = None

        exp._is_dirty = False
        exp._is_config_dirty = False

        return exp

    @json_property()
    def id(self):
        return self._id

    @json_property()
    def suite_id(self):
        return self._suite_id

    @suite_id.setter
    def suite_id(self, suite_id):
        self._suite_id = suite_id
        self._register_change()

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
        Retrieve one or more Experiments.
        
        :param id: The id (str or UUID) of the Experiment to retrieve
        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of Experiments returned, as well as which properties and child-objects to \
        fill for the returned Experiments
        :return: An Experiment or list of Experiments (depending on whether 'id' was specified) with \
        basic properties and child-objects assigned as specified by 'query_criteria'
        """
        if id and not isinstance(id, uuid.UUID):
            try:
                id = uuid.UUID(id)
            except ValueError:
                raise ValueError('Invalid id: {0}'.format(id))

        qc_params = query_criteria.to_param_dict(Experiment) if query_criteria else {}

        path = '/Experiments{0}'.format('/' + str(id) if id else '')
        resp = Client.get(path
                          , params = qc_params)

        json_resp = resp.json()

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('Experiment Response:')
        #     logger.debug(json.dumps(json_resp, indent=4))

        if 'Experiments' not in json_resp or \
                ( id is not None and len(json_resp['Experiments']) != 1 ):
            logger.debug(json_resp)
            raise RuntimeError('Malformed Experiments retrieve response!')

        exps = []

        for exp_json in json_resp['Experiments']:
            exp_json = cls.rest2py(exp_json)

            # if logger.isEnabledFor(logging.DEBUG):
            #     logger.debug('Experiment:')
            #     logger.debug(json.dumps(exp_json, indent=4))

            exp = Experiment.__internal_factory__(**exp_json)
            exps.append(exp)

        if id is not None:
            return exps[0]
        else:
            return exps

    def refresh(self, query_criteria=None):
        """
        Update properties of an existing Experiment from the server.

        :param query_criteria: A QueryCriteria object specifying which properties and child-objects \
        to refresh on the Experiment
        """
        if not self._id:
            raise RuntimeError('Can\'t refresh an Experiment that hasn\'t been saved!')

        exp = self.get(id=self.id, query_criteria=query_criteria)

        # if exp.id:                           self._id = exp.id
        if exp.name is not None:             self._name = exp.name
        if exp.suite_id is not None:         self._suite_id = exp.suite_id
        if exp.description is not None:      self._description = exp.description
        if exp.owner is not None:            self._owner = exp.owner
        if exp.date_created is not None:     self._date_created = exp.date_created
        if exp.last_modified is not None:    self._last_modified = exp.last_modified

        if exp.tags is not None:             self._tags = exp.tags
        if exp.configuration is not None:    self._configuration = exp.configuration

    def get_simulations(self, query_criteria=None):
        """
        Retrieve Simulations contained in this Experiment.

        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of Simulations returned, as well as which properties and child-objects to \
        fill for the returned Simulations
        :return: A list of Simulations with basic properties and child-objects assigned as specified \
        by 'query_criteria'
        """
        if not self._id:
            raise RuntimeError('Invalid call to get_simulations(); Experiment hasn\'t been saved yet')

        qc = copy.copy(query_criteria) if query_criteria else QueryCriteria()
        qc = qc.where('experiment_id={0}'.format(str(self._id)))

        return Simulation.get(query_criteria=qc)

    def save(self):
        """
        Save a single Experiment.  If it's a new Experiment, an id is automatically assigned.
        """
        if not self._is_dirty:
            logger.info('Experiment has not been altered... no point in saving it!')
            return

        if not self._id:
            exp_to_save = self
        else:
            exp_to_save = self.__internal_factory__(id=self._id,
                                                    name=self._name,
                                                    suite_id=self._suite_id,
                                                    description=self._description,
                                                    configuration=self._configuration if self._is_config_dirty else None)

        save_exp = SerializableEntity.convertToDict(exp_to_save, include_hidden_props=True)

        # indentval = 4 if logger.isEnabledFor(logging.DEBUG) else None

        json_str = json.dumps({'Experiments': [ save_exp ] },
                              # indent=indentval,
                              default=lambda obj:
                                            obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                            else str(obj) if isinstance(obj, uuid.UUID)
                                            else obj.name if isinstance(obj, Enum)
                                            else obj)

        resp = Client.post('/Experiments'
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
