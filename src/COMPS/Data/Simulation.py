from __future__ import print_function
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
import copy
import inspect
from functools import reduce
from COMPS import Client, default_callback_print_args
from COMPS.Data import Configuration, SimulationFile, HpcJob, AssetFile, AssetManager
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, parse_ISO8601_date, convert_if_string
from COMPS.Data.AssetManager import EntityType
from COMPS.Data.RelatableEntity import RelatableEntity
from COMPS.Data.TaggableEntity import TaggableEntity
from COMPS.Data.CommissionableEntity import CommissionableEntity

logger = logging.getLogger(__name__)

@json_entity()
class Simulation(TaggableEntity, CommissionableEntity, RelatableEntity, SerializableEntity):
    """
    Represents a single simulation run.

    Contains various basic properties accessible by getters (and, in some cases, +setters):

    * id
    * +experiment_id
    * +name
    * +description
    * owner
    * date_created
    * last_modified
    * state
    * error_message

    Also contains "child objects" (which must be specifically requested for retrieval using the
    QueryCriteria.select_children() method of QueryCriteria):

    * tags
    * configuration
    * files
    * hpc_jobs
    """

    __max_sim_batch_count = 100
    __max_sim_batch_request_size_kb = 38912     # 38 MiB
    __max_entity_retrieval_count = 100000

    try:
        __save_semaphore = multiprocessing.Semaphore(4)  # no. of concurrent threads that can save sims
    except (ModuleNotFoundError, ImportError):
        logger.warning('Unable to create process-local semaphore; proceeding, but without simulation save constraints!')
        import dummy_threading
        __save_semaphore = dummy_threading.Semaphore()

    __tls = threading.local()

    def __init__(self, name, experiment_id=None, description=None, configuration=None):
        if not name:
            raise RuntimeError('Simulation has not been initialized properly; non-null name required.')

        self._id = None
        self._name = name
        self._experiment_id = experiment_id
        self._description = description
        self._owner = Client.auth_manager().username
        self._date_created = None
        self._last_modified = None
        self._state = None
        self._error_message = None
        self._tags = None
        self._configuration = configuration
        self._files = ()
        self._hpc_jobs = None

        self._is_dirty = None       # these will be set in _register_change() below
        self._is_config_dirty = None
        self._tmp_file_parts = []

        self._register_change(config_changed=(configuration is not None))

    @classmethod
    def __internal_factory__(cls, id=None, name=None, experiment_id=None, description=None, owner=None,
                             date_created=None, last_modified=None, state=None, error_message=None,
                             tags=None, configuration=None, files=None, hpc_jobs=None):
        sim = cls.__new__(cls)

        sim._id = convert_if_string(id, uuid.UUID)
        sim._name = name
        sim._experiment_id = convert_if_string(experiment_id, uuid.UUID)
        sim._description = description
        sim._owner = owner
        sim._date_created = convert_if_string(date_created, parse_ISO8601_date)
        sim._last_modified = convert_if_string(last_modified, parse_ISO8601_date)
        sim._state = convert_if_string(state, lambda x: SimulationState[x])
        sim._error_message = error_message
        sim._tags = tags

        if configuration:
            if isinstance(configuration, Configuration):
                sim._configuration = configuration
            else:
                config_json = Configuration.rest2py(configuration)
                sim._configuration = Configuration(**config_json)
        else:
            sim._configuration = None

        if files:
            sim._files = tuple(SimulationFile.__internal_factory__(**(SimulationFile.rest2py(f))) for f in files)
            # sim._files = [ SimulationFile.__internal_factory__(**(SimulationFile.rest2py(f))) for f in files ]
        else:
            sim._files = None

        if hpc_jobs:
            sim._hpc_jobs = tuple(HpcJob.__internal_factory__(**(HpcJob.rest2py(j))) for j in hpc_jobs)
            # sim._hpc_jobs = [ HpcJob.__internal_factory__(**(HpcJob.rest2py(j))) for j in hpc_jobs ]
        else:
            sim._hpc_jobs = None

        sim._is_dirty = False
        sim._is_config_dirty = False
        sim._tmp_file_parts = []

        return sim

    @json_property()
    def id(self):
        return self._id

    @json_property()
    def experiment_id(self):
        return self._experiment_id

    @experiment_id.setter
    def experiment_id(self, experiment_id):
        self._experiment_id = experiment_id
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

    @json_property('SimulationState')
    def state(self):
        return self._state

    @json_property()
    def error_message(self):
        return self._error_message

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

    @json_property()
    def files(self):
        return self._files

    @json_property('HPCJobs')
    def hpc_jobs(self):
        return self._hpc_jobs

    ########################

    @classmethod
    def get(cls, id=None, query_criteria=None):
        """
        Retrieve one or more Simulations.

        :param id: The id (str or UUID) of the Simulation to retrieve
        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of Simulations returned, as well as which properties and child-objects to \
        fill for the returned Simulations
        :return: A Simulation or list of Simulations (depending on whether 'id' was specified) with \
        basic properties and child-objects assigned as specified by 'query_criteria'
        """
        if id and not isinstance(id, uuid.UUID):
            try:
                id = uuid.UUID(id)
            except ValueError:
                raise ValueError('Invalid id: {0}'.format(id))

        qc_params = query_criteria.to_param_dict(Simulation) if query_criteria else {}
        user_handling_paging = any(f in qc_params for f in ['count', 'offset'])
        qc_params['count'] = min(Simulation.__max_entity_retrieval_count, qc_params.get('count', Simulation.__max_entity_retrieval_count))

        path = '/Simulations{0}'.format('/' + str(id) if id else '')
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

                if total_val > Simulation.__max_entity_retrieval_count:
                    raise RuntimeError('Unable to retrieve entire data-set (try paging); the maximum simulations currently retrievable is ' +
                                       str(Simulation.__max_entity_retrieval_count))
            except (IndexError, ValueError) as e:
                logger.debug(e.message)
                raise RuntimeError('Invalid Content-Range response header: ' + str(cr))

        json_resp = resp.json()

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('Simulation Response:')
        #     logger.debug(json.dumps(json_resp, indent=4))

        if 'Simulations' not in json_resp or \
                ( id is not None and len(json_resp['Simulations']) != 1 ):
            logger.debug(json_resp)
            raise RuntimeError('Malformed Simulations retrieve response!')

        sims = []

        for sim_json in json_resp['Simulations']:
            sim_json = cls.rest2py(sim_json)

            # if logger.isEnabledFor(logging.DEBUG):
            #     logger.debug('Simulation:')
            #     logger.debug(json.dumps(sim_json, indent=4))

            sim = Simulation.__internal_factory__(**sim_json)
            sims.append(sim)

        if id is not None:
            return sims[0]
        else:
            return sims

    def refresh(self, query_criteria=None):
        """
        Update properties of an existing Simulation from the server.

        :param query_criteria: A QueryCriteria object specifying which properties and child-objects \
        to refresh on the Simulation
        """
        if not self._id:
            raise RuntimeError('Can\'t refresh a Simulation that hasn\'t been saved!')

        sim = self.get(id=self.id, query_criteria=query_criteria)

        # if sim.id:                          self._id = sim.id
        if sim.name is not None:            self._name = sim.name
        if sim.experiment_id is not None:   self._experiment_id = sim.experiment_id
        if sim.description is not None:     self._description = sim.description
        if sim.owner is not None:           self._owner = sim.owner
        if sim.date_created is not None:    self._date_created = sim.date_created
        if sim.last_modified is not None:   self._last_modified = sim.last_modified
        if sim.state is not None:           self._state = sim.state
        if sim.error_message is not None:   self._error_message = sim.error_message

        if sim.tags is not None:            self._tags = sim.tags
        if sim.configuration is not None:   self._configuration = sim.configuration
        if sim.files is not None:           self._files = sim.files
        if sim.hpc_jobs is not None:        self._hpc_jobs = sim.hpc_jobs

    def save(self, return_missing_files=False, save_semaphore=None):
        """
        Save a single Simulation.  If it's a new Simulation, an id is automatically assigned.

        :param return_missing_files: A boolean that determines the behavior when the Simulation \
        being saved contains a SimulationFile to be saved by md5 checksum (i.e. without \
        uploading the data) that is not yet in COMPS.  If true, when there are such files, \
        return an array of UUIDs representing the md5 checksums of the missing files.  If \
        false, raise an error when there are any such files.
        """
        if not self._is_dirty:
            logger.info('Simulation has not been altered... no point in saving it!')
            return

        prepped_self = Simulation.__prep_sim(self)
        estimated_sim_size = Simulation.__estimate_simulation_size(prepped_self)

        # Check if sim exceeds the request-size limit
        if False and estimated_sim_size + 4096 >= Simulation.__max_sim_batch_request_size_kb * 1024:
            logger.debug('sim: {0}'.format(str(self)))
            logger.debug('estimated_sim_size: {0}'.format(estimated_sim_size))
            raise RuntimeError('Simulation size exceeds single-sim limit!')

        untracked_ids = Simulation.__save_batch([prepped_self], return_missing_files, save_semaphore)

        if untracked_ids:
            return untracked_ids

        Simulation._get_dirty_list().remove(self)

    @classmethod
    def get_save_semaphore(cls):
        return cls.__save_semaphore

    @staticmethod
    def save_all(save_batch_callback=lambda: print('.', **default_callback_print_args), return_missing_files=False, save_semaphore=None):
        """
        Batch-save all unsaved Simulations.

        Simulations are saved in batches of at most '__max_sim_batch_count' and with a maximum request
        size of '__max_sim_batch_request_size_kb'.

        :param save_batch_callback: Callback to call whenever a request to save a batch of Simulations completes. \
        Default behavior is to print a single '.' to the console.  If the callback supplied takes 1 argument, the \
        number of Simulations saved so far will be passed when it is called.
        :param return_missing_files: A boolean that determines the behavior when any of the Simulations \
        being saved contains a SimulationFile to be saved by md5 checksum (i.e. without uploading the data) \
        that is not yet in COMPS.  If true, when there are such files, return an array of UUIDs representing \
        the md5 checksums of the missing files.  If false, raise an error when there are any such files.
        """
        if len(Simulation._get_dirty_list()) == 0:
            logger.info('No pending new simulations to batch-save!')
            return

        dirty_list = Simulation._get_dirty_list()

        num_sims_processed = 0
        estimated_sim_size = 0
        estimated_request_size = 4096   # generous overhead for HTTP headers, headers and '[' + ']' for base-entity
                                        # multipart section, and final multipart ending "footer"
        max_batch_count = min(len(dirty_list), Simulation.__max_sim_batch_count)
        prepped_sim = None
        prepped_sims = []

        if save_batch_callback:
            num_callback_args = len(inspect.getfullargspec(save_batch_callback).args)

        logger.info('Saving simulations')

        while num_sims_processed < len(dirty_list):
            sim = dirty_list[num_sims_processed]

            if not sim._is_dirty:
                logger.info('Skipping save for simulation {0} (already up-to-date).'.format(sim._id))
                num_sims_processed += 1
                continue

            if not prepped_sim:
                prepped_sim = Simulation.__prep_sim(sim)
                estimated_sim_size = Simulation.__estimate_simulation_size(prepped_sim)

            # add 2 because of ', ' between sims in the base-entity section
            if estimated_sim_size + estimated_request_size + 2 < Simulation.__max_sim_batch_request_size_kb * 1024:
                prepped_sims.append(prepped_sim)
                num_sims_processed += 1
                estimated_request_size += estimated_sim_size
                prepped_sim = None
                estimated_sim_size = 0

            # We want to try to save the batch now if 1 of the following 3 conditions is met:
                # - we reached maximum batch count
                # - we reached maximum batch size
                # - this is the last sim
            if len(prepped_sims) == max_batch_count or \
                    estimated_sim_size != 0 or \
                    num_sims_processed == len(dirty_list):

                if len(prepped_sims) == 0:
                    # one sim already exceeds the limit.  Raise an error and bail...
                    logger.debug('sim: {0}'.format(str(sim)))
                    logger.debug('estimated_sim_size: {0}'.format(estimated_sim_size))
                    raise RuntimeError('Simulation size exceeds single-sim limit!')

                # ready to send this batch!
                logger.debug("Ready to send single batch of {0} sims".format(len(prepped_sims)))

                untracked_ids = Simulation.__save_batch(prepped_sims, return_missing_files, save_semaphore)

                if untracked_ids:
                    del Simulation._get_dirty_list()[:num_sims_processed-len(prepped_sims)]
                    return untracked_ids

                if save_batch_callback:
                    if num_callback_args == 0:
                        save_batch_callback()
                    elif num_callback_args == 1:
                        save_batch_callback(num_sims_processed)

                prepped_sims = []
                estimated_request_size = 4096   # set back to initial value (w/ overhead)

        del Simulation._get_dirty_list()[:]

        return

    @staticmethod
    def __prep_sim(sim):
        if not sim._id:
            tmp_sim = copy.copy(sim)
        else:
            tmp_sim = Simulation.__internal_factory__(id=sim._id,
                                                      name=sim._name,
                                                      experiment_id=sim._experiment_id,
                                                      description=sim._description,
                                                      configuration=sim._configuration if sim._is_config_dirty else None)

        if len(sim._tmp_file_parts) > 0:
            tmp_sim._files = tuple( fi[0] for fi in sim._tmp_file_parts )

        save_sim = SerializableEntity.convertToDict(tmp_sim, include_hidden_props=True)

        # indentval = 4 if logger.isEnabledFor(logging.DEBUG) else None

        json_str = json.dumps(save_sim,
                              # indent=indentval,
                              default=lambda obj:
                                            obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                            else str(obj) if isinstance(obj, uuid.UUID)
                                            else obj.name if isinstance(obj, Enum)
                                            else obj)

        return (sim, json_str)

    @staticmethod
    def __estimate_simulation_size(prepped_sim):
        estimated_size = len(prepped_sim[1])    # Length contributed by this sim in the base-entity section

        for fp in filter(lambda x: x[1] is not None, prepped_sim[0]._tmp_file_parts):
            estimated_size += 135               # Length of multipart headers for a file, minus the actual value for 'Content-Type'
            estimated_size += len(fp[1][1][2])  # The value for 'Content-Type'
            estimated_size += len(fp[1][1][1])  # Length of the data for this file

        return estimated_size

    @staticmethod
    def __save_batch(prepped_sims, return_missing_files=False, save_semaphore=None):
        if not save_semaphore:
            logger.debug('No save_semaphore passed in; using process-local semaphore')
            save_semaphore = Simulation.__save_semaphore

        joinstr = ', ' #', {0}'.format('\n' if logger.isEnabledFor(logging.DEBUG) else '') \
        base_entity_str = joinstr.join(prepped_sim[1] for prepped_sim in prepped_sims)

        files_to_send = [ ('not_a_file', ('Simulations', '[' + base_entity_str + ']', 'application/json')) ]

        files_to_send.extend(reduce(lambda x, y: x + y, [ [ fp[1] for fp in prepped_sim[0]._tmp_file_parts if fp[1] is not None ] for prepped_sim in prepped_sims ]))

        with save_semaphore:
            resp = Client.post('/Simulations'
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

        if not ids or len(ids) != len(prepped_sims):
            logger.debug(json_resp)
            raise RuntimeError('Malformed Simulations save response!')

        for i in range(len(prepped_sims)):
            sim = prepped_sims[i][0]

            sim._is_dirty = False
            sim._is_config_dirty = False
            sim._tmp_file_parts = []

            if not sim._id:
                sim._id = uuid.UUID(ids[i])
                sim._state = SimulationState.Created
            elif sim._id != uuid.UUID(ids[i]):
                raise RuntimeError('Response Simulation Id doesn\'t match expected value!!!  {0} != {1}'.format(sim._id, ids[i]))

    def add_file(self, simulationfile, file_path=None, data=None, upload_callback=lambda: print('.', **default_callback_print_args)):
        """
        Add a SimulationFile to a Simulation.

        The contents of the file to add can be specified either by providing a path to the file
        or by providing the actual data as a byte-array.  Alternately, if the file/data is already in
        COMPS, you can skip uploading it again and just provide a SimulationFile that contains
        the md5 checksum of the data.

        If the file exceeds AssetManager.large_asset_upload_threshold bytes in size, the file will be
        uploaded immediately, separately from the saving of the main Simulation. This allows saving
        of arbitrarily-large files while avoiding potential timeouts or having to start from scratch in
        case the upload is interrupted by network issues.

        NOTE: providing both file/data and an md5 is considered invalid, as providing the md5 implies
        the caller knows the file/data is already in COMPS and doesn't need to be uploaded again.

        :param simulationfile: A SimulationFile containing the metadata for the file to add.
        :param file_path: The path to the file to add.
        :param data: The actual bytes of data to add.
        :param upload_callback: Callback to call whenever a large file upload completes saving of a \
        chunk of the file.  Default behavior is to print a single '.' to the console.  If the callback \
        supplied takes 1 argument, the number of bytes saved so far will be passed when it is called.
        """
        provided_md5 = simulationfile.md5_checksum is not None

        # Check only one of these three values is provided...
        if bool(provided_md5) + bool(file_path) + bool(data is not None) != 1:
            raise ValueError('Invalid argument(s): must provide (only) one of simulationfile.md5_checksum, file_path, or data')

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
                simulationfile._md5_checksum = uuid.UUID(md5_checksum_str)

                datasize = tmp_datastream.seek(0, os.SEEK_END)
                tmp_datastream.seek(0)

                if datasize > AssetManager.large_asset_upload_threshold:
                    AssetManager.upload_large_asset(simulationfile._md5_checksum, tmp_datastream, upload_callback)
                    provided_md5 = True  # we've uploaded it, no need to do so as part of the main entity save

            logger.debug('md5 checksum for file {0} is {1}'.format(simulationfile.file_name, str(simulationfile.md5_checksum)))

            self._files += (simulationfile,)

            if not provided_md5:
                tmp_file_tuple = (str(simulationfile.md5_checksum), (simulationfile.file_name, tmp_datastream.read(), AssetFile.get_media_type_from_filename(simulationfile.file_name)))
                self._tmp_file_parts.append((simulationfile, tmp_file_tuple))
            else:
                self._tmp_file_parts.append((simulationfile, None))
        finally:
            if tmp_datastream:
                tmp_datastream.close()

        self._register_change()

    def retrieve_output_files(self, paths, job=None, as_zip=False):
        """
        Retrieve output files associated with this Simulation.

        This essentially combines the functionality of retrieve_output_file_info() and
        retrieve_output_filess_from_info(), and can be used if user doesn't care about
        specific metadata related to the files being retrieved.

        :param paths: Partial paths (relative to the working directory) of the output files to retrieve.  If \
        'as_zip' is true, this can be None/empty or not specified, and all output files will be included in \
        the zip returned.
        :param job: The HpcJob associated with the given Simulation to retrieve assets for.  If not \
        specified, will default to the last HpcJob chronologically.
        :param as_zip: A boolean controlling whether the output files are returned individually or as \
        a single zip-file (useful for attaching to an e-mail, etc).
        :return: If 'as_zip' is true, returns a single byte-array of a zip-file; otherwise, returns a \
        list of byte-arrays of the output files retrieved, in the same order as the 'paths' parameter.
        """

        if (paths is None or len(paths) == 0) and not as_zip:
            raise RuntimeError('Can\'t specify empty/None \'paths\' argument unless \'as_zip\' is True.')

        metadata = self.retrieve_output_file_info(paths, job)

        byte_arrs = self.retrieve_output_files_from_info(metadata, job, as_zip)

        return byte_arrs

    def retrieve_output_file_info(self, paths, job=None):
        """
        Retrieve OutputFileMetadata about output files associated with this Simulation.

        :param paths: Partial paths (relative to the working directory) of the output files to retrieve.  If \
        None/empty or not specified, will default to return all output files.
        :param job: The HpcJob associated with the given Simulation to retrieve output files for.  If not \
        specified, will default to the last HpcJob chronologically.
        :return: A list of OutputFileMetadata objects for the output files to retrieve, in the same order \
        as the 'paths' parameter.
        """
        return AssetManager.retrieve_output_file_info(entity_type=EntityType.Simulations,
                                                      entity_id=self._id,
                                                      paths=paths,
                                                      job=job)

    def retrieve_output_files_from_info(self, metadata, job=None, as_zip=False):
        """
        Actually retrieve the output files associated with this Simulation.

        :param metadata: A list of OutputFileMetadata objects representing the output files to retrieve \
        associated with this Simulation.
        :param job: The HpcJob associated with the given Simulation to retrieve output files for.  This \
        should match the 'job' provided to the retrieve_output_file_info() call.  If not specified, will \
        default to the last HpcJob chronologically.
        :param as_zip: A boolean controlling whether the output files are returned individually or as \
        a single zip-file (useful for attaching to an e-mail, etc).
        :return: If 'as_zip' is true, returns a single byte-array of a zip-file; otherwise, returns a \
        list of byte-arrays of the output files retrieved, in the same order as the 'paths' parameter.
        """
        return AssetManager.retrieve_output_files_from_info(entity_type=EntityType.Simulations,
                                                            entity_id=self._id,
                                                            metadata=metadata,
                                                            job=job,
                                                            as_zip=as_zip)

    @staticmethod
    def static_retrieve_output_files(sim_id, paths, job=None, as_zip=False):
        s = Simulation.__internal_factory__(id=sim_id)
        return s.retrieve_output_files(paths, job, as_zip)

    def _register_change(self, config_changed=False):
        if not self._is_dirty:
            self._is_dirty = True
            Simulation._get_dirty_list().append(self)

        if config_changed and not self._is_config_dirty:
            self._is_config_dirty = True

    @staticmethod
    def _get_dirty_list():
        dl = getattr(Simulation.__tls, 'dirty_list', None)
        if not dl:
            Simulation.__tls.dirty_list = []
        return Simulation.__tls.dirty_list


class SimulationState(Enum):
    """
    An enumeration representing the current state of a Simulation
    """
    Created = 0               # Simulation has been saved to the database
    CommissionRequested = 1   # Simulation is ready to be processed by the job-service
    Provisioning = 2          # Simulation is being provisioned by the job-service (creating the working-directory, copying input files, etc)
    Commissioned = 3          # Simulation has been commissioned to be run and is awaiting processing resources
    Running = 4               # Simulation is currently running
    Retry = 5                 # Simulation failed and is going to be retried by the job-service
    Succeeded = 6             # Simulation completed successfully
    Failed = 7                # Simulation failed and will not go through any (more) retries
    CancelRequested = 8       # Simulation cancellation was requested
    Canceled = 9              # Simulation was successfully canceled
