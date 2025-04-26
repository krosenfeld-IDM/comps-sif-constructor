from enum import Enum
import json, uuid
from datetime import date, datetime
import logging
from future.utils import raise_from

from COMPS import Client
from COMPS.Data.BaseEntity import get_entity_type
# from COMPS.Data.Simulation import SimulationState

logger = logging.getLogger(__name__)

class TaggableEntity(object):

    def set_tags(self, tags):
        """
        Set the tag key/value pairs associated with this entity.

        If the entity has any existing tags, they will be replaced by the tags specified.  If this is a new entity,
        tags will not be updated until the entity is saved, otherwise tags are updated immediately.

        :param tags: A dictionary containing the key/value tag-string pairs to set.
        """
        if not self._id:
            TaggableEntity._validate_tags(tags)
            self._tags = tags   # JPS : should we create a copy here?  If someone uses the same underlying object, could they change it before we save?
            self._register_change()
            return

        self._save_tags(tags, TagOperationMode.Replace)

    def merge_tags(self, tags):
        """
        Merge the given tag key/value pairs with existing tags for this entity.

        Any tag keys that already have an existing tag with that key specified for the entity will have
        their values replaced by the value specified.  Any tag keys that don't already exist for the entity
        will be added with their specified value.

        :param tags: A dictionary containing the key/value tag-string pairs to merge.
        """
        self._save_tags(tags, TagOperationMode.Merge)

    def delete_tags(self, tags):
        """
        Delete the given tag keys for this entity.

        :param tags: A dictionary containing the key tag-strings to delete (Note: values are ignored).
        """
        self._save_tags(tags, TagOperationMode.Delete)

    def _save_tags(self, tags, tag_op_mode):
        et = get_entity_type(self.__class__)

        if not self._id:
            raise RuntimeError('Can\'t {0} tags on {1} {2} that hasn\'t been saved!'.format(tag_op_mode.name.lower(),
                                                                                            et.article,
                                                                                            et.name))

        TaggableEntity._validate_tags(tags)

        path = '/{0}s/{1}/tags'.format(et.name, str(self._id))
        resp = Client.post(path,
                           json={'Tags': tags, 'OperationMode': tag_op_mode.name})

    @staticmethod
    def _validate_tags(tags):
        try:
            s = json.dumps(tags,
                           default=lambda obj:
                                           obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                           else str(obj) if isinstance(obj, uuid.UUID)
                                           else obj.name if isinstance(obj, Enum)
                                           else obj)
        except ValueError as ve:
            # probably circular reference

            logger.debug('Error attempting to serialize tags')
            logger.debug(ve)

            for val in tags.values():
                if val is not None and not isinstance(val, (int,float,str,bool)):
                    logger.debug(f'Potentially bad tag value: {str(val)} - type: {type(val)}')

            raise_from(RuntimeError('Error attempting to serialize tags; tags values that are not of primitive type can cause this.  See COMPS_log.log for more details about the bad value'), None)

    # if not isinstance(tags, dict) or any([ val is not None and not any(isinstance(val, t) for t in [int,float,str,bool]) for val in tags.values()]):
        #     logger.debug(f'Invalid tags: {str(tags)}')
        #     if not isinstance(tags, dict):
        #         logger.debug('tags is not a dict!')
        #     else:
        #         for val in tags.values():
        #             if val is not None and not any(isinstance(val, t) for t in [int,float,str,bool]):
        #                 logger.debug(f'Invalid tag: {str(val)} - type: {type(val)}')
        #     raise RuntimeError('Invalid tags; tags must be a dictionary with all values being of string/numerical type or null')


class TagOperationMode(Enum):
    Merge = 1
    Replace = 2
    Delete = 3
