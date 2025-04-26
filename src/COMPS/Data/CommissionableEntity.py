import logging
from COMPS import Client
from COMPS.Data.BaseEntity import get_entity_type
# from COMPS.Data.Simulation import SimulationState

logger = logging.getLogger(__name__)

class CommissionableEntity(object):

    def commission(self):
        """
        Commission an entity.

        If called on a Suite/Experiment, this attempts to commission all contained Simulations
        currently in SimulationState.Created.
        If called on a Simulation, this attempts to commission that Simulation.  Only applicable if
        it is currently in SimulationState.Created.
        If called on a WorkItem, this attempts to commission that WorkItem.  Only applicable if
        it is currently in WorkItemState.Created.
        """
        self._set_state('CommissionRequested')

    def cancel(self):
        """
        Cancel a running entity.

        If called on a Suite/Experiment, this attempts to cancel all contained Simulations
        currently in an 'active' state:

        * SimulationState.CommissionRequested
        * SimulationState.Provisioning
        * SimulationState.Commissioned
        * SimulationState.Running
        * SimulationState.Retry

        If called on a Simulation, this attempts to commission that Simulation.  Only applicable if
        it is currently in an 'active' state; see above.
        If called on a WorkItem, this attempts to commission that WorkItem.  Only applicable if
        it is currently in an 'active' state:

        * WorkItemState.CommissionRequested
        * WorkItemState.Commissioned
        * WorkItemState.Validating
        * WorkItemState.Running
        * WorkItemState.Waiting
        * WorkItemState.ResumeRequested
        * WorkItemState.Resumed
        """
        self._set_state('CancelRequested')

    def _set_state(self, set_state):
        from COMPS.Data.Simulation import SimulationState
        from COMPS.Data.WorkItem import WorkItemState

        et = get_entity_type(self.__class__)

        if et.name == 'WorkItem':
            enumcls = WorkItemState
        else:
            enumcls = SimulationState

        set_state = enumcls[set_state]

        path = '/{0}s/{1}/State/{2}'.format(et.name, str(self._id), set_state.name)
        resp = Client.put(path,
                          data=None)

        if et.has_state:
            self._state = set_state

    def delete(self, expire_now=False):
        """
        "Soft-delete" this entity.

        This entity record and all associated files, etc, will be marked for deletion in COMPS.  They will
        remain for some period of time before being permanently deleted, but will no longer be returned by
        the COMPS service or visible in the UI.

        If called on a Suite/Experiment, this delete also applies to all contained Experiments/Simulations.

        :param expire_now: If this is set to True, this entity will be eligible for permanent deletion \
        immediately (though depending on deletion activity in the system, it may still be a while before \
        it's fully deleted).

        """
        et = get_entity_type(self.__class__)

        if not self._id:
            raise RuntimeError('Can\'t delete {0} {1} that hasn\'t been saved!'.format(et.article, et.name))

        path = '/{0}s/{1}'.format(et.name, str(self._id))
        resp = Client.delete(path, params = {'expirenow':True} if expire_now else None)
