import os
import io
import sys
import json
from datetime import date, datetime
import logging
from enum import Enum
import uuid
from hashlib import md5
import copy
import inspect
from COMPS import Client, AuthManager, default_callback_print_args
from COMPS.Data import AssetFile, QueryCriteria
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, parse_ISO8601_date, convert_if_string
from COMPS.Data import AssetManager
from COMPS.Data.RelatableEntity import RelatableEntity
from COMPS.Data.TaggableEntity import TaggableEntity
from COMPS.Data.AssetCollectionFile import AssetCollectionFile

logger = logging.getLogger(__name__)

@json_entity()
class AssetCollection(TaggableEntity, RelatableEntity, SerializableEntity):
    """
    Represents a collection of Assets.

    Once saved, an AssetCollection is immutable, other than modifying tags. It contains
    various properties accessible by getters:

    * id
    * date_created

    It also contains "child objects" (which must be specifically requested for retrieval using the
    QueryCriteria.select_children() method of QueryCriteria):

    * tags
    * assets
    """

    __max_ac_batch_file_count = 100
    __max_ac_request_size_kb = 407552   # 398 MiB
    __max_entity_retrieval_count = 100000

    def __init__(self):

        self._id = None
        self._date_created = None
        self._tags = None
        self._assets = ()

        self._tmp_file_parts = []

    @classmethod
    def __internal_factory__(cls, id=None, date_created=None, tags=None, assets=None):
        ac = cls.__new__(cls)

        ac._id = convert_if_string(id, uuid.UUID)
        ac._date_created = convert_if_string(date_created, parse_ISO8601_date)
        ac._tags = tags

        if assets:
            ac._assets = tuple(AssetCollectionFile.__internal_factory__(**(AssetCollectionFile.rest2py(af))) for af in assets)
        else:
            ac._assets = None

        ac._tmp_file_parts = []

        return ac

    @json_property()
    def id(self):
        return self._id

    @json_property()
    def date_created(self):
        return self._date_created

    @json_property()
    def tags(self):
        return self._tags       # todo: immutable dict?

    @json_property()
    def assets(self):
        return self._assets

    ########################

    @classmethod
    def get(cls, id=None, query_criteria=None):
        """
        Retrieve one or more AssetCollections.

        :param id: The id (str or UUID) of the AssetCollection to retrieve
        :param query_criteria: A QueryCriteria object specifying basic property filters and tag-filters \
        to apply to the set of AssetCollections returned, as well as which properties and child-objects to \
        fill for the returned AssetCollections
        :return: An AssetCollection or list of AssetCollections (depending on whether 'id' was specified) with \
        basic properties and child-objects assigned as specified by 'query_criteria'
        """
        if id and not isinstance(id, uuid.UUID):
            try:
                id = uuid.UUID(id)
            except ValueError:
                raise ValueError('Invalid id: {0}'.format(id))

        qc_params = query_criteria.to_param_dict(AssetCollection) if query_criteria else {}
        user_handling_paging = any(f in qc_params for f in ['count', 'offset'])
        qc_params['count'] = min(AssetCollection.__max_entity_retrieval_count, qc_params.get('count', AssetCollection.__max_entity_retrieval_count))

        path = '/AssetCollections{0}'.format('/' + str(id) if id else '')
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

                if total_val > AssetCollection.__max_entity_retrieval_count:
                    raise RuntimeError('Unable to retrieve entire data-set (try paging); the maximum asset collections currently retrievable is ' +
                                       str(AssetCollection.__max_entity_retrieval_count))
            except (IndexError, ValueError) as e:
                logger.debug(e.message)
                raise RuntimeError('Invalid Content-Range response header: ' + str(cr))

        json_resp = resp.json()

        # if logger.isEnabledFor(logging.DEBUG):
        #     logger.debug('AssetCollection Response:')
        #     logger.debug(json.dumps(json_resp, indent=4))

        if 'AssetCollections' not in json_resp or \
                ( id is not None and len(json_resp['AssetCollections']) != 1 ):
            logger.debug(json_resp)
            raise RuntimeError('Malformed AssetCollections retrieve response!')

        acs = []

        for ac_json in json_resp['AssetCollections']:
            ac_json = cls.rest2py(ac_json)

            # if logger.isEnabledFor(logging.DEBUG):
            #     logger.debug('AssetCollection:')
            #     logger.debug(json.dumps(ac_json, indent=4))

            ac = AssetCollection.__internal_factory__(**ac_json)
            acs.append(ac)

        if id is not None:
            return acs[0]
        else:
            return acs

    def refresh(self, query_criteria=None):
        """
        Update properties of an existing AssetCollection from the server.

        Since AssetCollections are mostly immutable, this is usually to retrieve/update
        fields or child-objects that weren't retrieved initially (e.g. assets).

        :param query_criteria: A QueryCriteria object specifying which properties and child-objects \
        to refresh on the AssetCollection
        """
        if not self._id:
            raise RuntimeError('Can\'t refresh an AssetCollection that hasn\'t been saved!')

        ac = self.get(id=self.id, query_criteria=query_criteria)

        # if ac.id:                          self._id = ac.id
        if ac.date_created is not None:    self._date_created = ac.date_created

        if ac.tags is not None:            self._tags = ac.tags
        if ac.assets is not None:          self._assets = ac.assets

    def save(self, return_missing_files=False, upload_files_callback=lambda: print('.', **default_callback_print_args)):
        """
        Save a single AssetCollection.  An id is automatically assigned upon successful save.

        When the AssetCollection contains a large number or large total size of new assets that
        need to be uploaded, this may be done in multiple "chunks".  This allows saving of
        arbitrarily-large AssetCollections while avoiding potential timeouts due to long
        processing time on the server.

        :param return_missing_files: A boolean that determines the behavior when the \
        AssetCollection being saved contains an AssetCollectionFile to be saved by md5 \
        checksum (i.e. without uploading the data) that is not yet in COMPS.  If true, \
        when there are such files, return an array of UUIDs representing the md5 checksums \
        of the missing files.  If false, raise an error when there are any such files.
        :param upload_files_callback: Callback to call whenever a batch of assets completes \
        uploading.  Default behavior is to print a single '.' to the console.  If the callback \
        supplied takes 1 argument, the number of assets saved so far will be passed when it is called.
        """
        if self._id is not None:
            raise RuntimeError('AssetCollection has already saved and cannot be altered.')

        save_ac = SerializableEntity.convertToDict(self) #, include_hidden_props=True)

        # indentval = 4 if logger.isEnabledFor(logging.DEBUG) else None

        json_str = json.dumps(save_ac,
                              # indent=indentval,
                              default=lambda obj:
                                            obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                            else str(obj) if isinstance(obj, uuid.UUID)
                                            else obj.name if isinstance(obj, Enum)
                                            else obj)

        total_file_data_to_send = sum(tfp[2] for tfp in self._tmp_file_parts)
        total_file_data_sent = 0

        if upload_files_callback:
            num_callback_args = len(inspect.getfullargspec(upload_files_callback).args)

        while len(json_str) + total_file_data_to_send > AssetCollection.__max_ac_request_size_kb * 1024 or \
                len(self._tmp_file_parts) > AssetCollection.__max_ac_batch_file_count:
            # The entity-request + all the files exceed the allowed request-size or recommended files-per-batch
            # count.  We need to upload some of the files separately until we're below the threshold.  If we
            # upload an empty AssetCollections array, the files get saved, but no AC is created.
            dummy_payload = [('not_a_file', ('AssetCollections', '[]', 'application/json'))]

            chunk_size = 0

            # 4096 = overhead for the empty AssetCollections array section
            while 4096 + chunk_size + self._tmp_file_parts[-1][2] < AssetCollection.__max_ac_request_size_kb * 1024 and \
                    len(dummy_payload) <= AssetCollection.__max_ac_batch_file_count:
                tfp = self._tmp_file_parts.pop()
                dummy_payload.append(tfp[1])
                chunk_size += tfp[2]

            if chunk_size == 0:
                raise RuntimeError('Asset size exceeds single-file limit!')

            logger.debug('Saving intermediate dummy AC ({0} files, {1} size)'.format(str(len(dummy_payload)), chunk_size))

            resp = Client.post('/AssetCollections'
                               , files=dummy_payload)

            total_file_data_sent += chunk_size

            if upload_files_callback:
                if num_callback_args == 0:
                    upload_files_callback()
                elif num_callback_args == 1:
                    upload_files_callback(total_file_data_sent)

            total_file_data_to_send -= chunk_size

        files_to_send = [ ('not_a_file', ('AssetCollections', '[' + json_str + ']', 'application/json')) ]

        files_to_send.extend([ fp[1] for fp in self._tmp_file_parts ])

        env = os.environ.get('COMPS_ENVIRONMENT')
        groupname = None

        if env:
            groupname = AuthManager.get_group_name_for_environment(env)
            logger.debug('Setting AC visibility for group: ' + groupname)

        resp = Client.post('/AssetCollections' + ( '?groupnames=' + groupname if groupname else '' )
                           , files=files_to_send
                           , http_err_handle_exceptions=[400])

        json_resp = resp.json()

        if resp.status_code == 400:
            untracked_ids = json_resp.get('UntrackedIds')
            if untracked_ids and len(untracked_ids) > 0 and return_missing_files:
                return [ uuid.UUID(x) for x in untracked_ids ]
            else:
                Client.raise_err_from_resp(resp)

        self._tmp_file_parts = []

        self._id = uuid.UUID(json_resp['Ids'][0])

    def add_asset(self, assetcollectionfile, file_path=None, data=None, upload_callback=lambda: print('.', **default_callback_print_args)):
        """
        Add an AssetCollectionFile to an AssetCollection.

        The contents of the file to add can be specified either by providing a path to the file
        or by providing the actual data as a byte-array.  Alternately, if the file/data is already in
        COMPS, you can skip uploading it again and just provide an AssetCollectionFile that contains
        the md5 checksum of the data.

        If the asset exceeds AssetManager.large_asset_upload_threshold bytes in size, the asset will be
        uploaded immediately, separately from the saving of the main AssetCollection. This allows saving
        of arbitrarily-large assets while avoiding potential timeouts or having to start from scratch in
        case the upload is interrupted by network issues.

        NOTE: this can only be called for not-yet-saved AssetCollections, since AssetCollections are
        immutable once saved, other than modifying tags.

        NOTE: providing both file/data and an md5 is considered invalid, as providing the md5 implies
        the caller knows the file/data is already in COMPS and doesn't need to be uploaded again.

        :param assetcollectionfile: An AssetCollectionFile containing the metadata for the file to add.
        :param file_path: The path to the file to add.
        :param data: The actual bytes of data to add.
        :param upload_callback: Callback to call whenever a large asset upload completes saving of a \
        chunk of the asset.  Default behavior is to print a single '.' to the console.  If the callback \
        supplied takes 1 argument, the number of bytes saved so far will be passed when it is called.
        """
        if self._id is not None:
            raise RuntimeError('AssetCollection has already saved and cannot be altered.')

        provided_md5 = assetcollectionfile.md5_checksum is not None

        # Check only one of these three values is provided...
        if bool(provided_md5) + bool(file_path) + bool(data is not None) != 1:
            raise ValueError('Invalid argument(s): must provide (only) one of assetcollectionfile.md5_checksum, file_path, or data')

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
                assetcollectionfile._md5_checksum = uuid.UUID(md5_checksum_str)

                datasize = tmp_datastream.seek(0, os.SEEK_END)
                tmp_datastream.seek(0)

                if datasize > AssetManager.large_asset_upload_threshold:
                    AssetManager.upload_large_asset(assetcollectionfile._md5_checksum, tmp_datastream, upload_callback)
                    provided_md5 = True  # we've uploaded it, no need to do so as part of the main entity save

            logger.debug('md5 checksum for file {0} is {1}'.format(assetcollectionfile.file_name, str(assetcollectionfile.md5_checksum)))

            self._assets += (assetcollectionfile,)

            if not provided_md5:
                tmp_file_tuple = (str(assetcollectionfile.md5_checksum), (assetcollectionfile.file_name, tmp_datastream.read(), AssetFile.get_media_type_from_filename(assetcollectionfile.file_name)))
                # calculate how many bytes this file will take up in the request...
                # multipart headers overhead + length of the Content-Type + length of the actual data
                total_size_in_request = 135 + len(tmp_file_tuple[1][2]) + len(tmp_file_tuple[1][1])
                self._tmp_file_parts.append((assetcollectionfile, tmp_file_tuple, total_size_in_request))
        finally:
            if tmp_datastream:
                tmp_datastream.close()


    def retrieve_as_zip(self):
        """
        Retrieve assets associated with this AssetCollection as a single zip-file.

        :return: returns a single byte-array of a zip-file.
        """
        if self._assets is None or self._assets[0].uri is None:
            tmp_ac = copy.copy(self)
            tmp_ac.refresh(QueryCriteria().select_children('assets'))
        else:
            tmp_ac = self

        return AssetManager.retrieve_asset_files(tmp_ac.assets, as_zip=True)

    @staticmethod
    def static_retrieve_as_zip(ac_id):
        ac = AssetCollection.__internal_factory__(id=ac_id)
        return ac.retrieve_as_zip()

    def _register_change(self, config_changed=False):
        pass