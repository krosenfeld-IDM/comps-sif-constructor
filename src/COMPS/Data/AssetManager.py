import os
import re
import sys
import time
import logging
import inspect
from enum import Enum
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from COMPS import Client
from COMPS.Data import OutputFileMetadata

logger = logging.getLogger(__name__)

max_asset_zip_file_size = 1073741824  # 1 GB
large_asset_upload_threshold = 10485760  # 10 MB
asset_upload_chunk_size_default = 1048576  # 1 MB


def retrieve_asset_files(asset_files, as_zip=False):
    if as_zip:
        total_zip_size = 0
        retrieve_assets = []

        for af in asset_files:
            total_zip_size += af.length

        if total_zip_size > max_asset_zip_file_size:
            raise RuntimeError('Total size of requested files ({0}) exceeds maximum allowed ({1})' \
                               .format(total_zip_size, max_asset_zip_file_size))

        zip_md = _do_asset_zip_url_request(asset_files)

        logger.debug('adding zip download url = ' + zip_md.url)
        retrieve_assets.append(zip_md)
    else:
        retrieve_assets = asset_files

    byte_arrs = _retrieve_files_from_metadata(retrieve_assets, lambda x: x.url if as_zip else x.uri)

    return byte_arrs[0] if as_zip else byte_arrs

def retrieve_output_file_info(entity_type, entity_id, paths, job=None):
    query_params = {'flatten': 1}
    if job:
        if entity_type == EntityType.WorkItems:
            raise RuntimeError('Setting \'job\' parameter for WorkItem is not valid')
        query_params['hpcjobid'] = job._id

    req_path = "/asset/{0}/{1}/Output".format(entity_type.name, str(entity_id))
    resp = Client.get(req_path,
                      params=query_params)

    json_resp = resp.json()

    if 'Resources' not in json_resp:
        raise RuntimeError('Malformed Asset Service response!')

    ofmd_map = {}

    for ofmd_json in json_resp['Resources']:
        ofmd_json = OutputFileMetadata.rest2py(ofmd_json)

        # logger.debug('Asset:')
        # logger.debug(json.dumps(ofmd_json, indent=4))

        ofmd = OutputFileMetadata.__internal_factory__(**ofmd_json)

        file_path = ofmd.friendly_name if ofmd.path_from_root == '.' else ofmd.path_from_root + '/' + ofmd.friendly_name
        logger.debug('adding [{0} -> {1}] to map'.format(file_path, ofmd.friendly_name))
        ofmd_map[file_path.lower()] = ofmd

    if paths is None or len(paths) == 0:    # paths not specified, return everything
        return ofmd_map.values()

    file_info = []

    for p in paths:
        ofmd = ofmd_map.get(p.lower().replace('\\', '/'))

        if not ofmd:
            raise RuntimeError('Couldn\'t find file for path \'{0}\''.format(p))

        file_info.append(ofmd)

    return file_info

def retrieve_output_files_from_info(entity_type, entity_id, metadata, job=None, as_zip=False):
    if as_zip:
        if job and entity_type == EntityType.WorkItems:
            raise RuntimeError('Setting \'job\' parameter for WorkItem is not valid')

        total_zip_size = 0
        retrieve_files = []
        ids = []

        for ofmd in metadata:
            total_zip_size += ofmd.length
            ids.append(ofmd._id)

        if total_zip_size > max_asset_zip_file_size:
            raise RuntimeError('Total size of requested files ({0}) exceeds maximum allowed ({1})' \
                               .format(total_zip_size, max_asset_zip_file_size))

        zip_md = _do_output_zip_url_request(entity_type, entity_id, ids, job)

        logger.debug('adding zip download url = ' + zip_md.url)
        retrieve_files.append(zip_md)
    else:
        retrieve_files = metadata

    byte_arrs = _retrieve_files_from_metadata(retrieve_files, lambda x: x.url)

    return byte_arrs[0] if as_zip else byte_arrs

def retrieve_partial_output_file_from_info(metadata, startbyte, endbyte=None, actualrange=None):
    """
    Retrieve part of an output file from a Simulation or WorkItem.

    :param metadata: An OutputFileMetadata object representing the output files to retrieve; this \
    is likely obtained by calling the retrieve_output_file_info() method on Simulation or WorkItem.
    :param startbyte: An integer representing the first byte in the request range, or if negative, \
    the number of bytes at the end of the file to return (in which case, endbyte must be None).
    :param endbyte: An integer representing the last byte in the request range.  If this value is \
    None and startbyte is positive, this represents the end of the file.
    :param actualrange: An optional list argument which, if passed, will contain the start byte, \
    end byte, and total file-size upon return.  This is useful if requesting "the last N bytes \
    in the file" or "from byte N to the end" in order to know the exact bytes which were returned.
    :return: A byte-array of the partial output file retrieved.
    """
    rng_hdr_str = None

    if startbyte < 0 and endbyte is None:
        rng_hdr_str = f'bytes={str(startbyte)}'
    elif startbyte >= 0 and endbyte is None:
        rng_hdr_str = f'bytes={str(startbyte)}-'
    elif startbyte >= 0 and endbyte >= startbyte:
        rng_hdr_str = f'bytes={str(startbyte)}-{str(endbyte)}'
    else:
        logger.warning(f'Invalid format for partial file-retrival (sb:{str(startbyte)}, eb:{str(endbyte)}); just getting entire file')

    i = metadata.url.find('/asset/')
    if i == -1:
        raise RuntimeError('Unable to parse asset url: ' + metadata.url)

    resp = Client.get(metadata.url[i:],
                      headers={'Range': rng_hdr_str} if rng_hdr_str else {})

    if actualrange is not None:
        cr_toks = re.split(' |-|/', resp.headers['Content-Range'])
        actualrange += [int(t) for t in cr_toks[1:]]

    return resp.content

def upload_large_asset(checksum, datastream, status_callback=None):
    startbyte = 0

    logger.debug('Uploading large asset - {}'.format(str(checksum)))

    resp = Client.get('/upload/check/{}'.format(str(checksum)),
                      http_err_handle_exceptions=[404])

    if resp.status_code == 200:
        logger.debug('File already there; no need to upload it again')
        return
    elif resp.status_code == 206:
        respjson = resp.json()
        startbyte = respjson['Size']
        logger.debug('Found partial file already uploaded; starting upload from {}'.format(str(startbyte)))
    else:
        logger.debug('Asset not found on server; uploading from start')

    content_headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Range': None
    }

    totallen = datastream.seek(0, os.SEEK_END)
    datastream.seek(startbyte)

    if status_callback:
        num_callback_args = len(inspect.getfullargspec(status_callback).args)

    chunk_size = asset_upload_chunk_size_default
    chunk_startbyte = startbyte

    while True:
        data = datastream.read(chunk_size)
        if not data:
            break

        content_headers['Content-Range'] = 'bytes {}-{}/{}'.format(chunk_startbyte, chunk_startbyte + len(data) - 1, totallen)

        starttime = _get_time()

        Client.post('/upload/{0}'.format(str(checksum)),
                                    headers=content_headers, data=data)

        requesttime = _get_time() - starttime

        logger.debug('saved chunk - ' + content_headers['Content-Range'])

        if requesttime < 2.0:
            chunk_size <<= 1
            logger.debug('doubling chunksize to ' + str(chunk_size))
        elif requesttime > 10.0 and chunk_size > 65536:
            chunk_size >>= 1
            logger.debug('halving chunksize to ' + str(chunk_size))

        chunk_startbyte += len(data)

        # Should we do this before or after chunk save...?
        if status_callback:
            if num_callback_args == 0:
                status_callback()
            elif num_callback_args == 1:
                status_callback(chunk_startbyte)

    logger.debug('Finished uploading file')

def _retrieve_files_from_metadata(files_metadata, get_url_fn):
    byte_arrs = []

    for fmd in files_metadata:
        url = get_url_fn(fmd)
        i = url.find('/asset/')
        if i == -1:
            raise RuntimeError('Unable to parse asset url: ' + url)

        resp = Client.get(url[i:])  # tried "stream=True", but ran into issues with ZipFile.  Just do this for now...

        # stream = resp.raw

        byte_arrs.append(resp.content)

    return byte_arrs

def _do_output_zip_url_request(entity_type, entity_id, ids, job):
    query_params = {'zip': 1}
    if job:
        query_params['hpcjobid'] = job._id

    req_path = "/asset/{0}/{1}/Output".format(entity_type.name, str(entity_id))
    resp = Client.post(req_path,
                       json={'ContainerType': 'CompressedZip', 'Ids': [ str(ofid) for ofid in ids ]},
                       params=query_params)

    json_resp = resp.json()

    if 'Resources' not in json_resp or len(json_resp['Resources']) != 1:
        raise RuntimeError('Malformed Asset Service response!')

    ofmd_json = OutputFileMetadata.rest2py(json_resp['Resources'][0])

    # logger.debug('Asset:')
    # logger.debug(json.dumps(ofmd_json, indent=4))

    ofmd = OutputFileMetadata.__internal_factory__(**ofmd_json)

    return ofmd

def _do_asset_zip_url_request(asset_files):
    # query_params = {'zip': 1}

    entries = [ {
                    'FileNameForAsset': _combine_asset_path_and_file(af),
                    'MD5': str(af.md5_checksum)
                } for af in asset_files ]

    resp = Client.post("/ZipAssets",
                       json={'ContainerType': 'CompressedZip', 'Assets': entries}) #,
                       # params=query_params)

    json_resp = resp.json()

    if 'Resources' not in json_resp or len(json_resp['Resources']) != 1:
        raise RuntimeError('Malformed Asset Service response!')

    ofmd_json = OutputFileMetadata.rest2py(json_resp['Resources'][0])

    # logger.debug('Asset:')
    # logger.debug(json.dumps(ofmd_json, indent=4))

    ofmd = OutputFileMetadata.__internal_factory__(**ofmd_json)

    return ofmd

def _combine_asset_path_and_file(asset):
    if asset.relative_path is None or asset.relative_path == '':
        return asset.file_name
    else:
        return os.path.join(asset.relative_path, asset.file_name).replace('/','\\')


if sys.version_info[0] == 2 or \
        (sys.version_info[0] == 3 and sys.version_info[1] < 3):
    def _get_time():
        return time.clock()
else:
    def _get_time():
        return time.perf_counter()


class EntityType(Enum):
    Simulations = 0
    WorkItems = 1
