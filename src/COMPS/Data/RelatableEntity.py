import logging

from COMPS import Client

logger = logging.getLogger(__name__)

class RelatableEntity(object):

    def get_parent_related_workitems(self, relation_type=None):
        """
        Get all 'parent' workitems that this entity is related to.

        :param relation_type: A RelationType object specifying which parent related WorkItems \
        to filter to.  If none is specified, all parent related WorkItems are returned.
        """
        from COMPS.Data import WorkItem

        reltype_suffix = f'/Relation/{relation_type.name}' if relation_type else ''
        path = f'/WorkItems/RelatedEntityId/{str(self._id)}/Type/{self.__class__.__name__}{reltype_suffix}'

        resp = Client.get(path)

        json_resp = resp.json()

        parent_wis_info = json_resp.get('Parents')

        parent_wis = []
        for wi_info in parent_wis_info:
            parent_wis.append(WorkItem.get(id=wi_info['Id']))

        return parent_wis