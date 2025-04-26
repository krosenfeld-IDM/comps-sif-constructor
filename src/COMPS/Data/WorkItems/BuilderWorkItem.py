from COMPS.Data import WorkItem
from COMPS.Data.WorkItem import WorkerOrPluginKey
from COMPS.Data.SerializableEntity import json_entity

@json_entity()
class BuilderWorkItem(WorkItem):
    __workitem_type = 'Builder'
    __workitem_version = '1.0.0.0_RELEASE'
    __worker = WorkerOrPluginKey(__workitem_type, __workitem_version)

    def __init__(self, name, environment_name, description=None):
        # raise NotImplementedError('This is not implemented yet.  Please use the base WorkItem class.')
        super(BuilderWorkItem, self).__init__(name, BuilderWorkItem.__worker, environment_name, description)
