import os
import sys
import logging.config

from COMPS.Client import Client
from COMPS.AuthManager import AuthManager

current_dir = os.path.dirname(os.path.realpath(__file__))
logging.config.fileConfig(os.path.join(current_dir,'logging.ini'), disable_existing_loggers=False)

# __all__ = ['Data']


if sys.version_info[0] == 2 or \
        (sys.version_info[0] == 3 and sys.version_info[1] < 3):
    default_callback_print_args = {'end':''}
else:
    default_callback_print_args = {'end':'', 'flush':True}