import os
import sys
import logging
import argparse

from COMPS import Client
from COMPS.Data import Experiment, Simulation

logger = logging.getLogger(__name__)

##########################
# Modify this section to allow comps-util to populate the help output, dynamically load the utility, parse command-line arguments, etc

# Add some metadata about the utility here: 
#  - any aliases (in addition to the full utility name, which will be the filename) that you want to use to run this utility
#  - a short help message highlighting what the utility does
#  - a longer description of what the utility does, generally with more explanation of features
#  - an "epilog" with examples of how to use the utility (use '%(prog)s' as a substitute for the utility-name to handle different entry methods)
utility_metadata = {
    'aliases': [ 'alias1', 'alias2' ],
    'help': 'Do something amazing',
    'description': 'This utility is truly amazing.  Once I started using it, I could truly say my life was changed in ' +
                   'unexpected ways.' + os.linesep + os.linesep +
                   'You too can have that life-changing experience.  Just start using this.',
    'epilog': '''examples:
  %(prog)s foo bar
  %(prog)s three_easy_steps youll_never_guess_what_happened_next
'''
}

# This method will be called to do argument-parsing.
# For some help on what to put here, you can check out: https://docs.python.org/3/howto/argparse.html

def fill_parser(p):
    p.add_argument('someargument', help='Of course you have to pass this')
    p.add_argument('anotherargument', help='This is required too')

##########################
# Add your function to do the thing here.
# This can be called directly from script by doing:
#
#    from COMPS.utils.my_utility_name import do_the_thing
#    do_the_thing('foo','bar')
#
# (where "my_utility_name" is the full name of your utility and the name of this file after copying from the template)

def do_the_thing( someargument, anotherargument ):
    logger.info(f'Let\'s do this!')
    logger.info(f'Some Arg: {someargument}')
    logger.info(f'Another Arg: {anotherargument}')


##########################
# You need to implement a simple main() method to allow execution from comps-util

def main(args):
    Client.login(args.comps_server)
    get_files(args.experiment_id, args.filename.split(','), args.overwrite, args.casesensitive)
