from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity

@json_entity()
class Configuration(SerializableEntity):
    """
    Configuration properties associated with a Suite, Experiment, or Simulation.

    A Configuration object is an immutable object containing various properties 
    accessible by getters:

    * environment_name
    * simulation_input_args
    * working_directory_root
    * executable_path
    * node_group_name
    * maximum_number_of_retries
    * priority
    * min_cores
    * max_cores
    * exclusive
    * asset_collection_id

    Properties of a Configuration associated with a Simulation will override properties of a
    Configuration associated with an Experiment, either of which will override properties of a
    Configuration associated with a Suite.

    No properties are required at any given level in the Suite/Experiment/Simulation hierarchy,
    but in order to create and run a simulation, at least the environment_name and
    executable_name must be specified somewhere in the hierarchy.
    """

    def __init__(self, environment_name=None, simulation_input_args=None, working_directory_root=None,
                 executable_path=None, node_group_name=None, maximum_number_of_retries=None,
                 priority=None, min_cores=None, max_cores=None, exclusive=None, asset_collection_id=None):

        self._environment_name = environment_name
        self._simulation_input_args = simulation_input_args
        self._working_directory_root = working_directory_root
        self._executable_path = executable_path
        self._node_group_name = node_group_name
        self._maximum_number_of_retries = maximum_number_of_retries
        self._priority = priority
        self._min_cores = min_cores
        self._max_cores = max_cores
        self._exclusive = exclusive
        self._asset_collection_id = asset_collection_id


    @json_property()
    def environment_name(self):
        return self._environment_name

    @json_property()
    def simulation_input_args(self):
        return self._simulation_input_args

    @json_property()
    def working_directory_root(self):
        return self._working_directory_root

    @json_property()
    def executable_path(self):
        return self._executable_path

    @json_property()
    def node_group_name(self):
        return self._node_group_name

    @json_property()
    def maximum_number_of_retries(self):
        return self._maximum_number_of_retries

    @json_property()
    def priority(self):
        return self._priority

    @json_property()
    def min_cores(self):
        return self._min_cores

    @json_property()
    def max_cores(self):
        return self._max_cores

    @json_property()
    def exclusive(self):
        return self._exclusive

    @json_property()
    def asset_collection_id(self):
        return self._asset_collection_id
