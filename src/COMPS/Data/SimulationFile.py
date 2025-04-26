import os
import uuid
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, convert_if_string
from COMPS.Data.AssetFile import AssetFile

@json_entity()
class SimulationFile(AssetFile, SerializableEntity):
    """
    Represents metadata for a Simulation file.

    Contains various basic properties accessible by getters:

    * file_name
    * file_type
    * description
    * md5_checksum
    * length
    * uri

    'file_name', 'file_type' and (optionally) 'description' must be set on creation.
    """

    def __init__(self, file_name, file_type, description='', md5_checksum=None):

        super(SimulationFile, self).__init__(file_name, md5_checksum)

        self._file_type = file_type
        self._description = description

    @classmethod
    def __internal_factory__(cls, file_name=None, file_type=None, description=None, md5_checksum=None,
                             length=None, uri=None):
        sf = cls.__new__(cls)

        sf._file_name = file_name
        sf._file_type = file_type
        sf._description = description
        sf._md5_checksum = convert_if_string(md5_checksum, uuid.UUID)
        sf._length = length
        sf._uri = uri

        return sf

    @json_property()
    def file_type(self):
        return self._file_type

    @json_property()
    def description(self):
        return self._description
