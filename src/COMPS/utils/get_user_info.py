import os
import sys
import json
import logging
import argparse

from COMPS import Client

logger = logging.getLogger(__name__)

##########################
# Modify this section to allow comps-util to populate the help output, dynamically load the utility, parse command-line arguments, etc

# Add some metadata about the utility here: 
#  - any aliases (in addition to the full utility name, which will be the filename) that you want to use to run this utility
#  - a short help message highlighting what the utility does
#  - a longer description of what the utility does, generally with more explanation of features
#  - an "epilog" with examples of how to use the utility (use '%(prog)s' as a substitute for the utility-name to handle different entry methods)
utility_metadata = {
    'aliases': [ 'getuser' ],
    'help': 'Get information about a user',
    'description': 'Get information about a particular user of COMPS by providing their username',
    'epilog': '''examples:
  %(prog)s johndoe
'''
}

# This method will be called to do argument-parsing.
# For some help on what to put here, you can check out: https://docs.python.org/3/howto/argparse.html

def fill_parser(p):
    p.add_argument('username', help='Username of the user to get info for')

##########################

def get_user_info( username ):
    resp = Client.get('/users?format=json')

    userlist = resp.json()

    if userlist and len(userlist) > 0:
        for user in userlist["Users"]:
            if user["UserName"] == username:
                logger.info(json.dumps(user, indent=4))
                return user

    logger.info(f'User {username} not found')
    return None

##########################

def main(args):
    Client.login(args.comps_server)
    get_user_info(args.username)
