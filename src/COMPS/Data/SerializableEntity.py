import logging
from datetime import date, datetime
import pytz
from uuid import UUID
from enum import Enum
import json
import re

logger = logging.getLogger(__name__)

try:
    COMPS_STRING_TYPE = basestring    # doesn't exist in Python 3...
except NameError:
    COMPS_STRING_TYPE = str     # don't need basestring any more since all Python 3 strings are unicode

def convert_if_string(o, fn):
    return fn(o) if isinstance(o, COMPS_STRING_TYPE) else o

def json_entity(ignore_props=None):
    SerializableEntity._set_ignore_props(ignore_props if ignore_props else [])
    return json_entity_internal

def json_entity_internal(cls):
    if not issubclass(cls, SerializableEntity):
        raise RuntimeError('Error! Entity type {0} is decorated as @json_entity, but doesn\'nt inherit from SerializableEntity')
    cls._map_properties()

    return cls

def json_property(rename_str=None):
    SerializableEntity._add_prop_rename(rename_str)
    return json_property_internal

class json_property_internal(property):
    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super(json_property_internal, self).__init__(fget, fset, fdel, doc)
        if not fset and not fdel and not doc:   # if this is the initial call to the @decorator
            SerializableEntity._add_prop_name(fget.__name__)

def parse_ISO8601_date(date_str):
    return datetime.strptime(date_str[:-2] + 'Z', "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=pytz.UTC)

def parse_namedtuple_from_dict(d):
    return { SerializableEntity._pascal_to_snake_case(key) : value for key, value in d.items() }


class SerializableEntity(object):
    __convert_regex = re.compile('([a-z0-9])([A-Z])')

    __ignore_unknowns = True    # Could make this a per-class thing with a default of True, but just make it
                                # global for now unless we find we actually need it more granular...

    __prop_strs_map = {}
    __prop_ignore_map = {}
    __py2rest_property_map = {}
    __rest2py_property_map = {}

    __tmp_ignore_props = []
    __tmp_prop_name_strs = []
    __tmp_prop_rename_strs = []

    def __str__(self):
        d = SerializableEntity.convertToDict(self, use_property_map=False) #, includeNulls=True)
        json_str = json.dumps(d,
                              indent=4,
                              default=lambda obj:
                                            # obj.isoformat() + '0Z' if isinstance(obj, (date, datetime))
                                            str(obj) if isinstance(obj, (date, datetime, UUID, tuple))
                                            else obj.name if isinstance(obj, Enum)
                                            else obj)

        # return self.__class__.__name__ + ':\n' + json_str
        return json_str

    # def __unicode__(self):
    #     return unicode(self.__str__())

    def __repr__(self):
        return self.__str__()

    @classmethod
    def py2rest(cls, obj):
        prop_map = SerializableEntity.__py2rest_property_map[cls.__name__]
        if isinstance(obj, dict):
            return { prop_map[key] : obj[key] for key in obj }
        elif isinstance(obj, list):
            return [ prop_map[i] for i in obj ]
        else:
            raise NotImplementedError('Invalid type for py2rest argument.')

    @classmethod
    def rest2py(cls, obj):
        prop_map = SerializableEntity.__rest2py_property_map[cls.__name__]
        ignore_list = SerializableEntity.__prop_ignore_map[cls.__name__]
        if isinstance(obj, dict):
            return {prop_map[key]: obj[key] for key in obj
                        if key not in ignore_list and (key in prop_map or not SerializableEntity.__ignore_unknowns)}
        elif isinstance(obj, list):
            return [ prop_map[i] for i in obj ]
        else:
            raise NotImplementedError('Invalid type for rest2py argument.')

    @staticmethod
    def convertToDict(obj, use_property_map=True, include_nulls=False, include_hidden_props=False):
        cls = type(obj)
        if issubclass(cls, SerializableEntity):
            prop_map = SerializableEntity.__py2rest_property_map[cls.__name__] if use_property_map else None
            # logger.debug('prop_map - ' + str(prop_map))
            build_dict = {}
            for name in SerializableEntity.__prop_strs_map[cls.__name__]:
                if (name[0] != '_') or include_hidden_props:
                    attr = getattr(obj, name)
                    if attr is not None or include_nulls:
                        prop_name = prop_map[name] if prop_map else name
                        if isinstance(attr, (SerializableEntity, list, tuple)):
                            build_dict[prop_name] = SerializableEntity.convertToDict(attr, use_property_map, include_nulls, include_hidden_props)
                        else:
                            build_dict[prop_name] = attr
            return build_dict
        elif isinstance(obj, tuple) and hasattr(obj, '_fields'):  # namedtuple
            return obj._asdict()
        elif isinstance(obj, (list, tuple)):
            items = [ SerializableEntity.convertToDict(item, use_property_map, include_nulls, include_hidden_props) if item is not None else None for item in obj ]
            # items = []
            # for item in obj:
            #     if item is not None:
            #         items.append(SerializableEntity.convertToDict(item, use_property_map, include_nulls, include_hidden_props))
            #     else:
            #         items.append(None)
            return items
        else:
            return obj

    @classmethod
    def _map_properties(cls):
        if cls.__name__ not in SerializableEntity.__py2rest_property_map:
            # logger.debug('name_strs - ' + str(SerializableEntity.__tmp_prop_name_strs))
            # logger.debug('rename_strs - ' + str(SerializableEntity.__tmp_prop_rename_strs))

            rest_strs = [ t[1] if t[1] else SerializableEntity._snake_to_pascal_case(t[0])
                          for t in zip(SerializableEntity.__tmp_prop_name_strs, SerializableEntity.__tmp_prop_rename_strs) ]

            # logger.debug('rest_strs - ' + str(rest_strs))

            # logger.debug('ignore props - ' + str(SerializableEntity.__tmp_ignore_props))
            SerializableEntity.__prop_strs_map[cls.__name__] = SerializableEntity.__tmp_prop_name_strs
            SerializableEntity.__prop_ignore_map[cls.__name__] = SerializableEntity.__tmp_ignore_props

            # logger.debug('props - ' + str(SerializableEntity.__prop_strs_map[cls.__name__]))

            SerializableEntity.__py2rest_property_map[cls.__name__] = dict(
                zip(SerializableEntity.__tmp_prop_name_strs, rest_strs))
            SerializableEntity.__rest2py_property_map[cls.__name__] = dict(
                zip(rest_strs, SerializableEntity.__tmp_prop_name_strs))

            for parent_cls in cls.__bases__:
                if parent_cls.__name__ in SerializableEntity.__prop_strs_map:
                    SerializableEntity.__prop_strs_map[cls.__name__].extend(SerializableEntity.__prop_strs_map[parent_cls.__name__])
                    SerializableEntity.__prop_ignore_map[cls.__name__].extend(SerializableEntity.__prop_ignore_map[parent_cls.__name__])

                    SerializableEntity.__py2rest_property_map[cls.__name__].update(SerializableEntity.__py2rest_property_map[parent_cls.__name__])
                    SerializableEntity.__rest2py_property_map[cls.__name__].update(SerializableEntity.__rest2py_property_map[parent_cls.__name__])

            logger.debug(cls.__name__ + ' --> ' + str(SerializableEntity.__rest2py_property_map[cls.__name__]))

        SerializableEntity.__tmp_ignore_props = []
        SerializableEntity.__tmp_prop_name_strs = []
        SerializableEntity.__tmp_prop_rename_strs = []

    @staticmethod
    def _add_prop_rename(rename_str):
        SerializableEntity.__tmp_prop_rename_strs.append(rename_str)

    @staticmethod
    def _add_prop_name(name_str):
        SerializableEntity.__tmp_prop_name_strs.append(name_str)

    @staticmethod
    def _set_ignore_props(ignore_props):
        SerializableEntity.__tmp_ignore_props = ignore_props

    @staticmethod
    def _pascal_to_snake_case(conv_str):
        return SerializableEntity.__convert_regex.sub(r'\1_\2', conv_str).lower()

    @staticmethod
    def _snake_to_pascal_case(conv_str):
        words = conv_str.split('_')
        return ''.join(word.capitalize() for word in words)