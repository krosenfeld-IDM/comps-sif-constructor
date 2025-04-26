from enum import Enum

class Priority(Enum):
    """
    An enumeration representing the Priority to run at.
    """
    Lowest = 0
    BelowNormal = 1
    Normal = 2
    AboveNormal = 3
    Highest = 4
