import os
import sys
import logging
import argparse

# Future improvement could be creating a base-class for utilities to inherit from.  For now, we'll just keep it simple...

logger = logging.getLogger(__name__)

excludes = [ 'main.py' ]

commands = [ os.path.splitext(f)[0] for f in os.listdir(os.path.dirname(__file__)) if not f.startswith('__') and f.endswith('.py') and f not in excludes ]

progname = os.path.basename(sys.argv[0])
if progname == '__main__.py':
    progname = 'python -m COMPS'

main_desc_str = '''These are utilities for simple, common COMPS functionality that's built-in and easy to use.  They can be called directly from the command-line or from within scripts.

For more information on the specific utilities, see the help for the individual commands.
'''

class CustomFormatter(argparse.RawDescriptionHelpFormatter):
    def _metavar_formatter(self, action, default_metavar):
        if action.dest == 'command' and action.choices is not None:
            result = '<command>'
            def format(tuple_size):
                return (result, ) * tuple_size
            return format
        return super(CustomFormatter, self)._metavar_formatter(action, default_metavar)

    def _format_action(self, action):
        parts = super(CustomFormatter, self)._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = '\n'.join(parts.split('\n')[1:])
        return parts

class CustomCommandFormatter(argparse.RawDescriptionHelpFormatter):
    def _metavar_formatter(self, action, default_metavar):
        if action.choices is not None:
            result = action.dest
            def format(tuple_size):
                return (result, ) * tuple_size
            return format
        return super(CustomCommandFormatter, self)._metavar_formatter(action, default_metavar)

def main():
    parser = argparse.ArgumentParser(description=main_desc_str, prog=progname, formatter_class=CustomFormatter)
    subparsers = parser.add_subparsers(title='commands', dest='command')

    cmd_mod_map = {}

    sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

    logger.debug(f'Commands found: {str(commands)}')

    for cmd in commands:
        # If we just import like this:
        #    mod = __import__(cmd)
        # the module is imported without the full "namespace" (e.g. it's imported as "my_cool_utility"
        # instead of "COMPS.utils.my_cool_utility", which breaks logging.  Therefore, we have to do
        # this ugliness.  I'm sorry.
        mod = __import__('COMPS.utils.'+cmd).utils.__dict__[cmd]

        try:
            md = getattr(mod, 'utility_metadata')
            md_obj = type('', (object, ), md)

            p = subparsers.add_parser(cmd, formatter_class=CustomCommandFormatter, **md)
            p.add_argument('--comps-server','-srv', help=argparse.SUPPRESS, default='https://comps.idmod.org')
            mod.fill_parser(p)
            cmd_mod_map[cmd] = mod
            if hasattr(md_obj, 'aliases'):
                cmd_mod_map.update({alias:mod for alias in md_obj.aliases})
        except Exception as e:
            logger.error(f'Error loading \'{cmd}\' utility.  Skipping...')
            logger.debug(e, exc_info=True)
            continue


    if len(cmd_mod_map) == 0:
        print('No valid utilities found!')
        sys.exit(-1)

    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    args = parser.parse_args()

    # execute the appropriate utility
    cmd_mod_map[args.command].main(args)
    

if __name__ == '__main__':
    main()
