import uuid
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, convert_if_string

@json_entity(ignore_props=['Type','Items','MD5'])
class OutputFileMetadata(SerializableEntity):
    """
    Metadata associated with output files served by the COMPS asset service.
    """

    @classmethod
    def __internal_factory__(cls, _internal_id=None, length=None, friendly_name=None, path_from_root=None,
                             url=None, mime_type=None):
        amd = cls.__new__(cls)

        amd._id = convert_if_string(_internal_id, uuid.UUID)
        amd._length = length
        amd._friendly_name = friendly_name
        amd._path_from_root = path_from_root
        amd._url = url
        amd._mime_type = mime_type

        return amd

    @json_property('Id')
    def _internal_id(self):
        return self._id

    @json_property()
    def length(self):
        return self._length

    @json_property()
    def friendly_name(self):
        return self._friendly_name

    @json_property()
    def path_from_root(self):
        return self._path_from_root

    @json_property()
    def url(self):
        return self._url

    @json_property()
    def mime_type(self):
        return self._mime_type

