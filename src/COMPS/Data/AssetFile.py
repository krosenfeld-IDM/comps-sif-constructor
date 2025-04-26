import os
import uuid
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity
from COMPS.Data import AssetManager

__media_type_extension_map = {'.json': 'application/json',
                              '.xml': 'application/xml',
                              '.txt': 'text/plain',
                              '.csv': 'text/plain'}

# @staticmethod
def get_media_type_from_filename(filename):
    ext = os.path.splitext(filename)[1]
    return __media_type_extension_map.get(ext, 'application/octet-stream')


@json_entity()
class AssetFile(SerializableEntity):
    """
    A base-type for all files associated with certain entity-types.  This
    includes AssetCollectionFile (associated with an AssetCollection),
    SimulationFile (associated with a Simulation), and WorkItemFile
    (associated with a WorkItem).

    This is used only for adding properties to these file-types, and
    shouldn't be created directly (should probably be an ABC).
    """

    def __init__(self, file_name, md5_checksum=None):

        if md5_checksum and not isinstance(md5_checksum, uuid.UUID):
            try:
                md5_checksum = uuid.UUID(md5_checksum)
            except ValueError:
                raise ValueError('Invalid md5_checksum: {0}'.format(md5_checksum))

        if not file_name:
            raise ValueError('Invalid file_name: cannot be empty or None')

        self._file_name = os.path.basename(file_name)
        self._md5_checksum = md5_checksum
        self._length = None
        self._uri = None

    @json_property()
    def file_name(self):
        return self._file_name

    @json_property("MD5Checksum")
    def md5_checksum(self):
        return self._md5_checksum

    @json_property()
    def length(self):
        return self._length

    @json_property()
    def uri(self):
        return self._uri

    ########################

    def retrieve(self):
        return AssetManager.retrieve_asset_files([self])[0]
