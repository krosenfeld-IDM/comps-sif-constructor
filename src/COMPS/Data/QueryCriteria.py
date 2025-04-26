import re

class QueryCriteria(object):
    """
    A helper class to control query return-sets by filtering on basic properties and tags, as
    well as controlling which properties and child-objects to fill for returned objects.
    """

    def __init__(self):
        self._fields = []
        self._children = []
        self._filters = []
        self._tag_filters = []

        self._orderby = None
        self._offset = None
        self._count = None

        self._xparams = None

    @property
    def fields(self):
        return self._fields

    @property
    def children(self):
        return self._children

    @property
    def filters(self):
        return self._filters

    @property
    def tag_filters(self):
        return self._tag_filters

    @property
    def orderby(self):
        return self._orderby

    @property
    def offset(self):
        return self._offset

    @property
    def count(self):
        return self._count

    @property
    def xparams(self):
        return self._xparams

    def select(self, fields):
        """
        Set which basic properties to fill for returned objects.

        :param fields: A list of basic properties to fill; e.g. ['id','description'].
        :return: A reference to this object so calls can be chained.
        """
        self._fields.extend([fields] if not isinstance(fields, list) else fields)
        return self

    def select_children(self, children):
        """
        Set which child objects to fill for returned objects.

        :param children: A list of child objects to fill; e.g. ['tags','hpc_jobs'].
        :return: A reference to this object so calls can be chained.
        """
        self._children.extend([children] if not isinstance(children, list) else children)
        return self

    def where(self, filters):
        """
        Set filter criteria for basic properties.

        For string filter values, '~' is used for the "like"-operator (i.e. string-contains).
        For numeric filter values, standard arithmetic operators are allowed.

        :param filters: A list of basic property filter-criteria; e.g. ['name~Test','state=Failed'].
        :return: A reference to this object so calls can be chained.
        """
        self._filters.extend([filters] if not isinstance(filters, list) else filters)
        return self

    def where_tag(self, tag_filters):
        """
        Set filter criteria for tags.

        For string filter values, '~' is used for the "like"-operator (i.e. string-contains).
        For numeric filter values, standard arithmetic operators are allowed.

        :param tag_filters: A list of tag filter-criteria; e.g. ['Replicate=3','DiseaseType~Malaria'].
        :return: A reference to this object so calls can be chained.
        """
        self._tag_filters.extend([tag_filters] if not isinstance(tag_filters, list) else tag_filters)
        return self

    def orderby(self, orderby_field):
        """
        Set which basic property to sort returned results-set by.

        :param orderby_field: A string containing the basic property name to sort by.  By default, \
        ascending-sort is assumed, but descending-sort can be specified by appending a space and 'desc' \
        to this argument; e.g. 'date_created desc'.
        :return: A reference to this object so calls can be chained.
        """
        self._orderby = orderby_field
        return self

    def offset(self, offset_num):
        """
        Set the offset within the results-set to start returning results from.

        :param offset_num: An int to specify offset within the results-set.
        :return: A reference to this object so calls can be chained.
        """
        if type(offset_num) is not int:
            raise RuntimeError('Parameter \'offset_num\' must be an int')
        self._offset = offset_num
        return self

    def count(self, count_num):
        """
        Set the maximum number of results to return in the results-set.

        :param count_num: An int to specify maximum number of results to return.
        :return: A reference to this object so calls can be chained.
        """
        if type(count_num) is not int:
            raise RuntimeError('Parameter \'count_num\' must be an int')
        self._count = count_num
        return self

    def add_extra_params(self, xp_dict):
        """
        Set any parameters that aren't otherwise explicitly supported.  This allows taking advantage
        of future potential changes to COMPS even if pyCOMPS support is not yet implemented or using
        an older version of pyCOMPS.

        :param xp_dict: A dictionary of additional parameters and values to pass to the COMPS API.
        :return: A reference to this object so calls can be chained.
        """
        self._xparams = xp_dict
        return self

    def to_param_dict(self, ent_type):
        pd = {}

        if len(self._fields) > 0:
            pd['fields'] = ','.join(ent_type.py2rest(self._fields))

        if len(self._children) > 0:
            pd['children'] = ','.join(ent_type.py2rest(self._children))

        if len(self._filters) > 0:
            tups = [ (f, re.search(r'\W', f)) for f in self._filters ]

            keys = [ f[:r.start()] if r else f for f, r in tups ]
            vals = [ f[r.start():] if r else f for f, r in tups ]

            mod_filters = map(lambda x, y: x + y, ent_type.py2rest(keys), vals)

            pd['filters'] = ','.join(mod_filters)

        if len(self._tag_filters) > 0:
            pd['tagfilters'] = ','.join(self._tag_filters)

        if self._orderby:
            spl = self._orderby.split(' ')
            pd['orderby'] = ent_type.py2rest([spl[0]])[0] + ( ' ' + spl[1] if len(spl) > 1 else '' )

        if self._offset:
            pd['offset'] = self._offset

        if self._count:
            pd['count'] = self._count

        if self._xparams:
            pd = { **pd, **self._xparams }

        return pd
