import uuid
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, convert_if_string
from COMPS.Data.TaggableEntity import TaggableEntity
from COMPS.Data.AssetFile import AssetFile

@json_entity()
class AssetCollectionFile(AssetFile, TaggableEntity, SerializableEntity):
    """
    Represents a single Asset in an AssetCollection.

    Once created, an AssetCollectionFile is immutable, other than modifying tags. It contains
    various properties accessible by getters:

    * file_name
    * relative_path
    * md5_checksum
    * length
    * uri
    * tags

    The md5_checksum can be used as an id for the AssetCollectionFile.
    """

    def __init__(self, file_name=None, relative_path=None, md5_checksum=None, tags=None):

        super(AssetCollectionFile, self).__init__(file_name, md5_checksum)

        self._relative_path = relative_path
        self._tags = tags

    @classmethod
    def __internal_factory__(cls, file_name=None, relative_path=None, md5_checksum=None,
                             length=None, uri=None, tags=None):
        af = cls.__new__(cls)

        af._file_name = file_name
        af._relative_path = relative_path
        af._md5_checksum = convert_if_string(md5_checksum, uuid.UUID)
        af._length = length
        af._uri = uri
        af._tags = tags

        af._tmp_file_parts = []

        return af

    @json_property()
    def relative_path(self):
        return self._relative_path

    @json_property()
    def tags(self):
        return self._tags       # todo: immutable dict?
