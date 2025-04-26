from __future__ import print_function
from future.utils import raise_from
import os
import io
import sys
import json
from datetime import date, datetime
import logging
from enum import Enum
import uuid
from hashlib import md5
import threading
import multiprocessing
import os
import re
import copy
import inspect
from functools import reduce
from collections import namedtuple
from COMPS import Client, default_callback_print_args
from COMPS.Data import WorkItemFile, AssetFile, AssetManager, Priority, Simulation, Experiment, Suite, AssetCollection
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, parse_ISO8601_date, parse_namedtuple_from_dict, convert_if_string
from COMPS.Data.AssetManager import EntityType
from COMPS.Data.RelatableEntity import RelatableEntity
from COMPS.Data.TaggableEntity import TaggableEntity
from COMPS.Data.CommissionableEntity import CommissionableEntity

logger = logging.getLogger(__name__)

@json_entity()
class WorkItem(TaggableEntity, CommissionableEntity, RelatableEntity, SerializableEntity):
    """
    Represents a single work-item.

    Contains various basic properties accessible by getters (and, in some cases, +setters):

    * id
    * +name
    * +description
    * owner
    * date_created
    * last_modified
    * state
    * error_message
    * worker
    * environment_name
    * host_name
    * worker_instance_id
    * priority
    * working_directory
    * working_directory_size
    * asset_collection_id

    Also contains "child objects" (which must be specifically requested for retrieval using the
    QueryCriteria.select_children() method of QueryCriteria):

    * tags
    * files
    * plugins
    """

    __max_wi_batch_count = 100
    __max_wi_batch_request_size_kb = 38912     # 38 MiB
    __max_entity_retrieval_count = 100000

    try:
        __save_semaphore = multiprocessing.Semaphore(4)  # no. of concurrent threads that can save work-items
    except (ModuleNotFoundError, ImportError):
        logger.warning('Unable to create process-local semaphore; proceeding, but without work-item save constraints!')
        import dummy_threading
        __save_semaphore = dummy_threading.Semaphore()

    __tls = threading.local()

    def __init__(self, name, worker, environment_name, description=None, asset_collection_id=None, priority=None):
        if not name:
            raise RuntimeError('WorkItem has not been initialized properly; non-null name required.')

        if not environment_name:
            raise RuntimeError('WorkItem has not been initialized properly; non-null environment_name required.')

        if not worker or not worker.name or not worker.version:
            raise RuntimeError('WorkItem has not been initialized properly; valid \'worker\' required.')

        self._id = None
        self._name = name
        self._worker = worker
        self._environment_name = environment_name
        self._description = description
        self._owner = Client.auth_manager().username
        self._date_created = None
        self._last_modified = None
        self._state = None
        self._error_message = None
        self._host_name = None
        self._worker_instance_id = None
        self._priority = priority
        self._working_directory = None
        self._working_directory_size = None
        self._asset_collection_id = asset_collection_id

        self._tags = None
        self._files = ()
        self._plugins = None

        self._is_dirty = None       # this will be set in _register_change() below
        self._tmp_file_parts = []

        self._register_change()

    @classmethod
    def __internal_factory__(cls, id=None, name=None, worker=None, environment_name=None, description=None,
                             owner=None, date_created=None, last_modified=None, state=None, error_message=None,
                             host_name=None, worker_instance_id=None, priority=None, working_directory=None,
                             working_directory_size=None, asset_collection_id=None, tags=None, files=None,
                             plugins=None):
        wi = cls.__new__(cls)

        wi._id = convert_if_string(id, uuid.UUID)
        wi._name = name
        wi._worker = WorkerOrPluginKey(**parse_namedtuple_from_dict(worker)) if worker else None
        wi._environment_name = environment_name
        wi._description = description
        wi._owner = owner
        wi._date_created = convert_if_string(date_created, parse_ISO8601_date)
        wi._last_modified = convert_if_string(last_modified, parse_ISO8601_date)
        wi._state = convert_if_string(state, lambda x: WorkItemState[x])
        wi._error_message = error_message
        wi._host_name = host_name
        wi._worker_instance_id = convert_if_string(worker_instance_id, uuid.UUID)
        wi._priority = convert_if_string(priority, lambda x: Priority[x])
        wi._working_directory = working_directory
        wi._working_directory_size = working_directory_size
        wi._asset_collection_id = convert_if_string(asset_collection_id, uuid.UUID)

        wi._tags = tags

        if files:
            wi._files = tuple(WorkItemFile.__internal_factory__(**(WorkItemFile.rest2py(f))) for f in files)
            # wi._files = [ WorkItemFile.__internal_factory__(**(WorkItemFile.rest2py(f))) for f in files ]
        else:
            wi._files = None

        if plugins:
            wi._plugins = tuple(WorkerOrPluginKey(p) for p in plugins)
            # wi._plugins = [ WorkerOrPluginKey(p) for p in plugins ]
        else:
            wi._plugins = None

        wi._is_dirty = False
        wi._tmp_file_parts = []

        return wi

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
    def worker(self):
        return self._worker

    @json_property()
    def environment_name(self):
        return self._environment_name

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
    def state(self):
        return self._state

    @json_property()
    def error_message(self):
        return self._error_message

    @json_property()
    def host_name(self):
        return self._host_name

    @json_property()
    def worker_instance_id(self):
        return self._worker_instance_id

    @json_property()
    def priority(self):
        return self._priority

    @json_property()
    def working_directory(self):
        if 'COMPS_DATA_MAPPING' in os.environ:
            mapping = os.environ.get('COMPS_DATA_MAPPING').split(';')
            return re.sub(mapping[1].replace('\\', '\\\\'), mapping[0], self._working_directory, flags=re.IGNORECASE).replace('\\', '/')
        else:
            return self._working_directory

    @json_property()
    def working_directory_size(self):
        return self._working_directory_size

    @json_property()
    def asset_collection_id(self):
        return self._asset_collection_id

    @json_property()
    def tags(self):
        return self._tags       # todo: immutable dict?

    @json_property()
    def files(self):
        return self._files

    @json_property()
    def plugins(self):
        return self._plugins

    ########################

    @classmethod
    def get(cls, id=None, query_criteria=None):
        """
        Retrieve one or more WorkItems.

        :param id: The id (str or UUID) of the WorkItem to retrieve
        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of WorkItems returned, as well as which properties and child-objects to \
        fill for the returned WorkItems
        :return: A WorkItem or list of WorkItems (depending on whether 'id' was specified) with \
        basic properties and child-objects assigned as specified by 'query_criteria'
        """
        if id and not isinstance(id, uuid.UUID):
            try:
                id = uuid.UUID(id)
            except ValueError:
                raise ValueError('Invalid id: {0}'.format(id))

        qc_params = query_criteria.to_param_dict(WorkItem) if query_criteria else {}
        user_handling_paging = any(f in qc_params for f in ['count','offset'])
        qc_params['count'] = min(WorkItem.__max_entity_retrieval_count, qc_params.get('count', WorkItem.__max_entity_retrieval_count))

        path = '/WorkItems{0}'.format('/' + str(id) if id else '')
        resp = Client.get(path
                          , params = qc_params)

        cr = resp.headers.get('Content-Range')
        # If we got a Content-Range header in the response (meaning we didn't get the entire dataset back) and the user
        # isn't handling paging (as inferred by not having a 'count' or 'offset' argument), double-check to see if
        # we got the whole data-set (presumably not) and raise an error so the user knows.
        if cr and not user_handling_paging:
            try:
                toks = cr.replace('-','/').split('/')
                # from_val = int(toks[0])
                # to_val = int(toks[1])
                total_val = int(toks[2])

                if total_val > WorkItem.__max_entity_retrieval_count:
                    raise RuntimeError('Unable to retrieve entire data-set (try paging); the maximum work-items currently retrievable is ' +
                                       str(WorkItem.__max_entity_retrieval_count))
            except (IndexError, ValueError) as e:
                logger.debug(e.message)
                raise RuntimeError('Invalid Content-Range response header: ' + str(cr))

        json_resp = resp.json()

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('WorkItem Response:')
        #     logger.debug(json.dumps(json_resp, indent=4))

        if 'WorkItems' not in json_resp or \
                ( id is not None and len(json_resp['WorkItems']) != 1 ):
            logger.debug(json_resp)
            raise RuntimeError('Malformed WorkItems retrieve response!')

        wis = []

        for wi_json in json_resp['WorkItems']:
            wi_json = cls.rest2py(wi_json)

            # if logger.isEnabledFor(logging.DEBUG):
            #     logger.debug('WorkItem:')
            #     logger.debug(json.dumps(wi_json, indent=4))

            wi = WorkItem.__internal_factory__(**wi_json)
            wis.append(wi)

        if id is not None:
            return wis[0]
        else:
            return wis

    def refresh(self, query_criteria=None):
        """
        Update properties of an existing WorkItem from the server.

        :param query_criteria: A QueryCriteria object specifying which properties and child-objects \
        to refresh on the WorkItem
        """
        if not self._id:
            raise RuntimeError('Can\'t refresh a WorkItem that hasn\'t been saved!')

        wi = self.get(id=self.id, query_criteria=query_criteria)

        # if wi.id:                               self._id = wi.id
        if wi.name is not None:                 self._name = wi.name
        if wi.worker is not None:               self._worker = wi.worker
        if wi.environment_name is not None:     self._environment_name = wi.environment_name
        if wi.description is not None:          self._description = wi.description
        if wi.owner is not None:                self._owner = wi.owner
        if wi.date_created is not None:         self._date_created = wi.date_created
        if wi.last_modified is not None:        self._last_modified = wi.last_modified
        if wi.state is not None:                self._state = wi.state
        if wi.error_message is not None:        self._error_message = wi.error_message
        if wi.host_name is not None:            self._host_name = wi.host_name
        if wi.worker_instance_id is not None:   self._worker_instance_id = wi.worker_instance_id
        if wi.priority is not None:             self._priority = wi.priority
        if wi.working_directory is not None:    self._working_directory = wi.working_directory
        if wi.working_directory_size is not None: self._working_directory_size = wi.working_directory_size
        if wi.asset_collection_id is not None:  self._asset_collection_id = wi.asset_collection_id

        if wi.tags is not None:                 self._tags = wi.tags
        if wi.files is not None:                self._files = wi.files
        if wi.plugins is not None:              self._plugins = wi.plugins

    def get_related_work_items(self, relation_type=None):
        """
        Get a list of WorkItems related to this WorkItem

        :param relation_type: A RelationType object specifying which related WorkItems \
        to filter to.  If none is specified, all related WorkItems are returned.
        """
        return self._get_related_entities(WorkItem, relation_type).get('WorkItem', [])

    def get_related_suites(self, relation_type=None):
        """
        Get a list of Suites related to this WorkItem

        :param relation_type: A RelationType object specifying which related Suites \
        to filter to.  If none is specified, all related Suites are returned.
        """
        return self._get_related_entities(Suite, relation_type).get('Suite', [])

    def get_related_experiments(self, relation_type=None):
        """
        Get a list of Experiments related to this WorkItem

        :param relation_type: A RelationType object specifying which related Experiments \
        to filter to.  If none is specified, all related Experiments are returned.
        """
        return self._get_related_entities(Experiment, relation_type).get('Experiment', [])

    def get_related_simulations(self, relation_type=None):
        """
        Get a list of Simulations related to this WorkItem

        :param relation_type: A RelationType object specifying which related Simulations \
        to filter to.  If none is specified, all related Simulations are returned.
        """
        return self._get_related_entities(Simulation, relation_type).get('Simulation', [])

    def get_related_asset_collections(self, relation_type=None):
        """
        Get a list of AssetCollections related to this WorkItem

        :param relation_type: A RelationType object specifying which related AssetCollections \
        to filter to.  If none is specified, all related AssetCollections are returned.
        """
        return self._get_related_entities(AssetCollection, relation_type).get('AssetCollection', [])

    def _get_related_entities(self, cls=None, relation_type=None):
        query_params = {}

        if cls:
            query_params['RelatedObject'] = cls.__name__
        if relation_type:
            query_params['RelationType'] = relation_type.name

        path = '/WorkItems/{0}/Related'.format(str(self._id))
        resp = Client.get(path
                          , params = query_params)

        json_resp = resp.json()

        ent_map = { 'Simulation': Simulation,
                    'Experiment': Experiment,
                    'Suite': Suite,
                    'WorkItem': WorkItem,
                    'AssetCollection': AssetCollection }

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('WorkItem Related Response:')
        #     logger.debug(json.dumps(json_resp, indent=4))

        related_arr = json_resp.get('Related')

        related_map = {}
        if related_arr:
            for rel_entity in related_arr:
                enttype = rel_entity['ObjectType']
                if enttype not in related_map:
                    related_map[enttype] = []
                related_map[enttype].append(ent_map[enttype].get(id=rel_entity['Id']))

        return related_map

    def add_related_work_item(self, related_id, relation_type):
        """
        Add a relationship between this WorkItem and a related WorkItem

        :param related_id: The id (str or UUID) of the related WorkItem
        :param relation_type: The RelationType that describes how this WorkItem is \
        related to the related WorkItem
        """
        self._add_related_entity(WorkItem, related_id, relation_type)

    def add_related_suite(self, related_id, relation_type):
        """
        Add a relationship between this WorkItem and a related Suite

        :param related_id: The id (str or UUID) of the related Suite
        :param relation_type: The RelationType that describes how this WorkItem is \
        related to the related Suite
        """
        self._add_related_entity(Suite, related_id, relation_type)

    def add_related_experiment(self, related_id, relation_type):
        """
        Add a relationship between this WorkItem and a related Experiment

        :param related_id: The id (str or UUID) of the related Experiment
        :param relation_type: The RelationType that describes how this WorkItem is \
        related to the related Experiment
        """
        self._add_related_entity(Experiment, related_id, relation_type)

    def add_related_simulation(self, related_id, relation_type):
        """
        Add a relationship between this WorkItem and a related Simulation

        :param related_id: The id (str or UUID) of the related Simulation
        :param relation_type: The RelationType that describes how this WorkItem is \
        related to the related Simulation
        """
        self._add_related_entity(Simulation, related_id, relation_type)

    def add_related_asset_collection(self, related_id, relation_type):
        """
        Add a relationship between this WorkItem and a related AssetCollection

        :param related_id: The id (str or UUID) of the related AssetCollection
        :param relation_type: The RelationType that describes how this WorkItem is \
        related to the related AssetCollection
        """
        self._add_related_entity(AssetCollection, related_id, relation_type)

    def _add_related_entity(self, cls, related_id, relation_type):
        if not self._id:
            raise RuntimeError('Can\'t add related entity to WorkItem that hasn\'t yet been saved!')

        if not isinstance(related_id, uuid.UUID):
            try:
                related_id = uuid.UUID(related_id)
            except (AttributeError, ValueError):
                raise_from(ValueError('Invalid related_id: {0}.  Must pass a single (str or UUID) id'.format(str(related_id))), None)

        # /WorkItems/{Id}/Related/{RelationType}/{RelatedObject}/{RelatedObjectId}
        path = '/WorkItems/{0}/Related/{1}/{2}/{3}'.format(str(self._id),
                                                           relation_type.name,
                                                           cls.__name__,
                                                           str(related_id))
        resp = Client.post(path)

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('Save WorkItem Related Response:')
        #     logger.debug(json.dumps(resp.json(), indent=4))

    def save(self, return_missing_files=False, save_semaphore=None):
        """
        Save a single WorkItem.  If it's a new WorkItem, an id is automatically assigned.

        :param return_missing_files: A boolean that determines the behavior when the WorkItem \
        being saved contains a WorkItemFile to be saved by md5 checksum (i.e. without \
        uploading the data) that is not yet in COMPS.  If true, when there are such files, \
        return an array of UUIDs representing the md5 checksums of the missing files.  If \
        false, raise an error when there are any such files.
        """
        if not self._is_dirty:
            logger.info('WorkItem has not been altered... no point in saving it!')
            return

        prepped_self = WorkItem.__prep_wi(self)
        estimated_wi_size = WorkItem.__estimate_workitem_size(prepped_self)

        # Check if wi exceeds the request-size limit
        if False and estimated_wi_size + 4096 >= WorkItem.__max_wi_batch_request_size_kb * 1024:
            logger.debug('wi: {0}'.format(str(self)))
            logger.debug('estimated_wi_size: {0}'.format(estimated_wi_size))
            raise RuntimeError('WorkItem size exceeds single-workitem limit!')

        untracked_ids = WorkItem.__save_batch([prepped_self], return_missing_files, save_semaphore)

        if untracked_ids:
            return untracked_ids

        WorkItem._get_dirty_list().remove(self)

    @classmethod
    def get_save_semaphore(cls):
        return cls.__save_semaphore

    @staticmethod
    def save_all(save_batch_callback=lambda: print('.', **default_callback_print_args), return_missing_files=False, save_semaphore=None):
        """
        Batch-save all unsaved WorkItems.

        WorkItems are saved in batches of at most '__max_wi_batch_count' and with a maximum request
        size of '__max_wi_batch_request_size_kb'.

        :param save_batch_callback: Callback to call whenever a request to save a batch of WorkItems completes. \
        Default behavior is to print a single '.' to the console.  If the callback supplied takes 1 argument, the \
        number of WorkItems saved so far will be passed when it is called.
        :param return_missing_files: A boolean that determines the behavior when any of the WorkItems \
        being saved contains a WorkItemFile to be saved by md5 checksum (i.e. without uploading the data) \
        that is not yet in COMPS.  If true, when there are such files, return an array of UUIDs representing \
        the md5 checksums of the missing files.  If false, raise an error when there are any such files.
        """
        if len(WorkItem._get_dirty_list()) == 0:
            logger.info('No pending new work-items to batch-save!')
            return

        dirty_list = WorkItem._get_dirty_list()

        num_wis_processed = 0
        estimated_wi_size = 0
        estimated_request_size = 4096   # generous overhead for HTTP headers, headers and '[' + ']' for base-entity
                                        # multipart section, and final multipart ending "footer"
        max_batch_count = min(len(dirty_list), WorkItem.__max_wi_batch_count)
        prepped_wi = None
        prepped_wis = []

        if save_batch_callback:
            num_callback_args = len(inspect.getfullargspec(save_batch_callback).args)

        logger.info('Saving WorkItems')

        while num_wis_processed < len(dirty_list):
            wi = dirty_list[num_wis_processed]

            if not wi._is_dirty:
                logger.info('Skipping save for work-item {0} (already up-to-date).'.format(wi._id))
                num_wis_processed += 1
                continue

            if not prepped_wi:
                prepped_wi = WorkItem.__prep_wi(wi)
                estimated_wi_size = WorkItem.__estimate_workitem_size(prepped_wi)

            # add 2 because of ', ' between wis in the base-entity section
            if estimated_wi_size + estimated_request_size + 2 < WorkItem.__max_wi_batch_request_size_kb * 1024:
                prepped_wis.append(prepped_wi)
                num_wis_processed += 1
                estimated_request_size += estimated_wi_size
                prepped_wi = None
                estimated_wi_size = 0

            # We want to try to save the batch now if 1 of the following 3 conditions is met:
                # - we reached maximum batch count
                # - we reached maximum batch size
                # - this is the last wi
            if len(prepped_wis) == max_batch_count or \
                    estimated_wi_size != 0 or \
                    num_wis_processed == len(dirty_list):

                if len(prepped_wis) == 0:
                    # one wi already exceeds the limit.  Raise an error and bail...
                    logger.debug('wi: {0}'.format(str(wi)))
                    logger.debug('estimated_wi_size: {0}'.format(estimated_wi_size))
                    raise RuntimeError('WorkItem size exceeds single-workitem limit!')

                # ready to send this batch!
                logger.debug("Ready to send single batch of {0} work-items".format(len(prepped_wis)))

                untracked_ids = WorkItem.__save_batch(prepped_wis, return_missing_files, save_semaphore)

                if untracked_ids:
                    del WorkItem._get_dirty_list()[:num_wis_processed-len(prepped_wis)]
                    return untracked_ids

                if save_batch_callback:
                    if num_callback_args == 0:
                        save_batch_callback()
                    elif num_callback_args == 1:
                        save_batch_callback(num_wis_processed)

                prepped_wis = []
                estimated_request_size = 4096   # set back to initial value (w/ overhead)

        del WorkItem._get_dirty_list()[:]

        return

    @staticmethod
    def __prep_wi(wi):
        if not wi._id:
            tmp_wi = copy.copy(wi)
        else:
            tmp_wi = WorkItem.__internal_factory__(id=wi._id,
                                                   name=wi._name,
                                                   description=wi._description)

        if len(wi._tmp_file_parts) > 0:
            tmp_wi._files = tuple( fi[0] for fi in wi._tmp_file_parts )

        save_wi = SerializableEntity.convertToDict(tmp_wi, include_hidden_props=True)

        # indentval = 4 if logger.isEnabledFor(logging.DEBUG) else None

        json_str = json.dumps(save_wi,
                              # indent=indentval,
                              default=lambda obj:
                                            obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                            else str(obj) if isinstance(obj, uuid.UUID)
                                            else obj.name if isinstance(obj, Enum)
                                            else obj)

        return (wi, json_str)

    @staticmethod
    def __estimate_workitem_size(prepped_wi):
        estimated_size = len(prepped_wi[1])    # Length contributed by this workitem in the base-entity section

        for fp in filter(lambda x: x[1] is not None, prepped_wi[0]._tmp_file_parts):
            estimated_size += 135               # Length of multipart headers for a file, minus the actual value for 'Content-Type'
            estimated_size += len(fp[1][1][2])  # The value for 'Content-Type'
            estimated_size += len(fp[1][1][1])  # Length of the data for this file

        return estimated_size

    @staticmethod
    def __save_batch(prepped_wis, return_missing_files=False, save_semaphore=None):
        if not save_semaphore:
            logger.debug('No save_semaphore passed in; using process-local semaphore')
            save_semaphore = WorkItem.__save_semaphore

        joinstr = ', ' #', {0}'.format('\n' if logger.isEnabledFor(logging.DEBUG) else '') \
        base_entity_str = joinstr.join(prepped_wi[1] for prepped_wi in prepped_wis)

        files_to_send = [ ('not_a_file', ('WorkItems', '[' + base_entity_str + ']', 'application/json')) ]

        files_to_send.extend(reduce(lambda x, y: x + y, [ [ fp[1] for fp in prepped_wi[0]._tmp_file_parts if fp[1] is not None ] for prepped_wi in prepped_wis ]))

        with save_semaphore:
            resp = Client.post('/WorkItems'
                               , files=files_to_send
                               , http_err_handle_exceptions=[400])

        if resp.status_code == 400:
            untracked_ids = None
            try:
                json_resp = resp.json()
                untracked_ids = json_resp.get('UntrackedIds')
            except:
                pass
            if untracked_ids and len(untracked_ids) > 0 and return_missing_files:
                return [ uuid.UUID(x) for x in untracked_ids ]
            else:
                Client.raise_err_from_resp(resp)

        json_resp = resp.json()

        ids = json_resp.get('Ids')

        if not ids or len(ids) != len(prepped_wis):
            logger.debug(json_resp)
            raise RuntimeError('Malformed WorkItems save response!')

        for i in range(len(prepped_wis)):
            wi = prepped_wis[i][0]

            wi._is_dirty = False
            wi._tmp_file_parts = []

            if not wi._id:
                wi._id = uuid.UUID(ids[i])
                wi._state = WorkItemState.Created
            elif wi._id != uuid.UUID(ids[i]):
                raise RuntimeError('Response WorkItem Id doesn\'t match expected value!!!  {0} != {1}'.format(wi._id, ids[i]))

    def add_work_order(self, file_path=None, data=None):
        """
        Add the WorkOrder for a WorkItem.

        The contents of the WorkOrder file to add can be specified either by providing a path to the file
        or by providing the actual data as a string.

        :param file_path: The path to the work-order file to add.
        :param data: The actual bytes of work-order data to add.
        """
        fn = 'WorkOrder.json' if not file_path else os.path.basename(file_path)
        self.add_file(WorkItemFile(fn, 'WorkOrder', ''), file_path, data)

    def add_file(self, workitemfile, file_path=None, data=None, upload_callback=lambda: print('.', **default_callback_print_args)):
        """
        Add a WorkItemFile to a WorkItem.

        The contents of the file to add can be specified either by providing a path to the file
        or by providing the actual data as a byte-array.  Alternately, if the file/data is already in
        COMPS, you can skip uploading it again and just provide a WorkItemFile that contains
        the md5 checksum of the data.

        If the file exceeds AssetManager.large_asset_upload_threshold bytes in size, the file will be
        uploaded immediately, separately from the saving of the main WorkItem. This allows saving
        of arbitrarily-large files while avoiding potential timeouts or having to start from scratch in
        case the upload is interrupted by network issues.

        NOTE: providing both file/data and an md5 is considered invalid, as providing the md5 implies
        the caller knows the file/data is already in COMPS and doesn't need to be uploaded again.

        :param workitemfile: A WorkItemFile containing the metadata for the file to add.
        :param file_path: The path to the file to add.
        :param data: The actual bytes of data to add.
        :param upload_callback: Callback to call whenever a large file upload completes saving of a \
        chunk of the file.  Default behavior is to print a single '.' to the console.  If the callback \
        supplied takes 1 argument, the number of bytes saved so far will be passed when it is called.
        """
        provided_md5 = workitemfile.md5_checksum is not None

        # Check only one of these three values is provided...
        if bool(provided_md5) + bool(file_path) + bool(data is not None) != 1:
            raise ValueError('Invalid argument(s): must provide (only) one of workitemfile.md5_checksum, file_path, or data')

        tmp_datastream = None

        try:
            if file_path:
                tmp_datastream = open(file_path, 'rb')
            elif data is not None:
                if sys.version_info[0] >= 3 and isinstance(data, str):
                    raise ValueError('Argument \'data\' must be passed in as bytes (not a unicode string)')
                tmp_datastream = io.BytesIO(data)
            else:
                tmp_datastream = None

            if tmp_datastream is not None:
                md5calc = md5()

                while True:
                    datachunk = tmp_datastream.read(8192)
                    if not datachunk:
                        break
                    md5calc.update(datachunk)

                md5_checksum_str = md5calc.hexdigest()
                workitemfile._md5_checksum = uuid.UUID(md5_checksum_str)

                datasize = tmp_datastream.seek(0, os.SEEK_END)
                tmp_datastream.seek(0)

                if datasize > AssetManager.large_asset_upload_threshold:
                    AssetManager.upload_large_asset(workitemfile._md5_checksum, tmp_datastream, upload_callback)
                    provided_md5 = True  # we've uploaded it, no need to do so as part of the main entity save

            logger.debug('md5 checksum for file {0} is {1}'.format(workitemfile.file_name, str(workitemfile.md5_checksum)))

            self._files += (workitemfile,)

            if not provided_md5:
                tmp_file_tuple = (str(workitemfile.md5_checksum), (workitemfile.file_name, tmp_datastream.read(), AssetFile.get_media_type_from_filename(workitemfile.file_name)))
                self._tmp_file_parts.append((workitemfile, tmp_file_tuple))
            else:
                self._tmp_file_parts.append((workitemfile, None))
        finally:
            if tmp_datastream:
                tmp_datastream.close()

        self._register_change()

    def retrieve_output_files(self, paths, as_zip=False):
        """
        Retrieve output files associated with this WorkItem.

        This essentially combines the functionality of retrieve_output_file_info() and
        retrieve_output_filess_from_info(), and can be used if user doesn't care about
        specific metadata related to the files being retrieved.

        :param paths: Partial paths (relative to the working directory) of the output files to retrieve.  If \
        'as_zip' is true, this can be None/empty or not specified, and all output files will be included in \
        the zip returned.
        :param as_zip: A boolean controlling whether the output files are returned individually or as \
        a single zip-file (useful for attaching to an e-mail, etc).
        :return: If 'as_zip' is true, returns a single byte-array of a zip-file; otherwise, returns a \
        list of byte-arrays of the output files retrieved, in the same order as the 'paths' parameter.
        """

        if (paths is None or len(paths) == 0) and not as_zip:
            raise RuntimeError('Can\'t specify empty/None \'paths\' argument unless \'as_zip\' is True.')

        metadata = self.retrieve_output_file_info(paths)

        byte_arrs = self.retrieve_output_files_from_info(metadata, as_zip)

        return byte_arrs

    def retrieve_output_file_info(self, paths):
        """
        Retrieve OutputFileMetadata about output files associated with this WorkItem.

        :param paths: Partial paths (relative to the working directory) of the output files to retrieve.  If \
        None/empty or not specified, will default to return all output files.
        :return: A list of OutputFileMetadata objects for the output files to retrieve, in the same order \
        as the 'paths' parameter.
        """
        return AssetManager.retrieve_output_file_info(entity_type=EntityType.WorkItems,
                                                      entity_id=self._id,
                                                      paths=paths)

    def retrieve_output_files_from_info(self, metadata, as_zip=False):
        """
        Actually retrieve the output files associated with this WorkItem.

        :param metadata: A list of OutputFileMetadata objects representing the output files to retrieve \
        associated with this WorkItem.
        :param as_zip: A boolean controlling whether the output files are returned individually or as \
        a single zip-file (useful for attaching to an e-mail, etc).
        :return: If 'as_zip' is true, returns a single byte-array of a zip-file; otherwise, returns a \
        list of byte-arrays of the output files retrieved, in the same order as the 'paths' parameter.
        """
        return AssetManager.retrieve_output_files_from_info(entity_type=EntityType.WorkItems,
                                                            entity_id=self._id,
                                                            metadata=metadata,
                                                            as_zip=as_zip)

    @staticmethod
    def static_retrieve_output_files(workitem_id, paths, as_zip=False):
        wi = WorkItem.__internal_factory__(id=workitem_id)
        return wi.retrieve_output_files(paths, as_zip)


    def _register_change(self):
        if not self._is_dirty:
            self._is_dirty = True
            WorkItem._get_dirty_list().append(self)

    @staticmethod
    def _get_dirty_list():
        dl = getattr(WorkItem.__tls, 'dirty_list', None)
        if not dl:
            WorkItem.__tls.dirty_list = []
        return WorkItem.__tls.dirty_list


WorkerOrPluginKey = namedtuple('WorkerOrPluginKey', ['name', 'version'])

class WorkItemState(Enum):
    """
    An enumeration representing the current state of a WorkItem
    """
    Created = 0                # WorkItem has been saved to the database
    CommissionRequested = 5    # WorkItem is ready to be processed by the next available worker of the correct type
    Commissioned = 10          # WorkItem has been commissioned to a worker of the correct type and is beginning execution
    Validating = 30            # WorkItem is being validated
    Running = 40               # WorkItem is currently running
    Waiting = 50               # WorkItem is waiting for dependent items to complete
    ResumeRequested = 60       # Dependent items have completed and WorkItem is ready to be processed by the next available worker of the correct type
    CancelRequested = 80       # WorkItem cancellation was requested
    Canceled = 90              # WorkItem was successfully canceled
    Resumed = 100              # WorkItem has been claimed by a worker of the correct type and is resuming
    Canceling = 120            # WorkItem is in the process of being canceled by the worker
    Succeeded = 130            # WorkItem completed successfully
    Failed = 140               # WorkItem failed

class RelationType(Enum):
    """
    An enumeration representing the type of relationship for related entities
    """
    DependsOn = 0
    Created = 1