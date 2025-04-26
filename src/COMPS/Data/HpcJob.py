import os
import re
import uuid
from enum import Enum
from COMPS.Data import Priority, Configuration
from COMPS.Data.SerializableEntity import SerializableEntity, json_property, json_entity, parse_ISO8601_date, convert_if_string

@json_entity(ignore_props=['TaskState', 'TaskId'])
class HpcJob(SerializableEntity):
    """
    Represents a single HPC Job.

    Contains various properties accessible by getters:

    * job_id
    * job_state
    * priority
    * working_directory
    * output_directory_size
    * submit_time
    * start_time
    * end_time
    * error_message
    * configuration

    HpcJobs are created by the COMPS Job Service, so they're read-only, used for tracking HPC Jobs.

    Note: Tasks are not currently used in the COMPS system, so task properties are only there for
    future use.
    """
    
    @classmethod
    def __internal_factory__(cls, _internal_id=None, job_id=None, job_state=None, priority=None,
                             working_directory=None, output_directory_size=None, submit_time=None,
                             start_time=None, end_time=None, error_message=None, configuration=None):
        job = cls.__new__(cls)

        job._id = convert_if_string(_internal_id, uuid.UUID)
        job._job_id = job_id
        job._job_state = convert_if_string(job_state, lambda x: HpcState[x])
        job._priority = convert_if_string(priority, lambda x: Priority[x])
        job._working_directory = working_directory
        job._output_directory_size = output_directory_size
        job._submit_time = convert_if_string(submit_time, parse_ISO8601_date)
        job._start_time = convert_if_string(start_time, parse_ISO8601_date)
        job._end_time = convert_if_string(end_time, parse_ISO8601_date)
        job._error_message = error_message

        if configuration:
            config_json = Configuration.rest2py(configuration)
            job._configuration = Configuration(**config_json)
        else:
            job._configuration = None

        return job

    @json_property('Id')
    def _internal_id(self):
        return self._id

    @json_property()
    def job_id(self):
        return self._job_id

    @json_property()
    def job_state(self):
        return self._job_state

    @json_property()
    def priority(self):
        return self._priority

    @json_property()
    def working_directory(self):
        if 'COMPS_DATA_MAPPING' in os.environ:
            mapping = os.environ.get('COMPS_DATA_MAPPING').split(';')
            return re.sub(mapping[1].replace('\\', '\\\\'), mapping[0], self._working_directory, flags=re.IGNORECASE).replace('\\', '/')
        else:
            return self._working_directory

    @json_property()
    def output_directory_size(self):
        return self._output_directory_size

    @json_property()
    def submit_time(self):
        return self._submit_time

    @json_property()
    def start_time(self):
        return self._start_time

    @json_property()
    def end_time(self):
        return self._end_time

    @json_property()
    def error_message(self):
        return self._error_message

    @json_property()
    def configuration(self):
        return self._configuration


class HpcState(Enum):
    """
    An enumeration representing the state of the job, as tracked by the HPC cluster.
    """
    NotSet = 0
    Configuring = 1            # the HPC cluster is configuring the job environment
    Submitted = 2              # the HPC cluster is submitting the job
    Validating = 4             # the Job is being validated for resource usage
    ExternalValidation = 8     # check for premissions and certificates
    Queued = 16                # the job is in the queue
    Running = 32               # the job has entered the running state
    Finishing = 64             # the job is finishing the post processing
    Finished = 128             # Exit state - job was successful
    Failed = 256               # Exit state - job failed
    Canceled = 512             # Exit state - job was cancelled
    Canceling = 1024           # Job is attempted to be canceled
