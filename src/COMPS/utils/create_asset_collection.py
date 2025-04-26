import os
import logging
from hashlib import md5

from COMPS import Client
from COMPS.Data import AssetCollection, AssetCollectionFile

logger = logging.getLogger(__name__)

##########################

utility_metadata = {
    'aliases': [ 'createac' ],
    'help': 'Create an asset collection from a local directory',
    'description': 'This utility creates an asset collection from all the files in the specified directory, mirroring ' +
                    'the directory hierarchy.  Any files not already known to COMPS will be automatically identified ' +
                    'and uploaded; files already known will not be uploaded again, but just referenced by checksum ' +
                    'during asset collection creation (consequently, time to run can vary widely depending on count ' +
                    'and size of new files being uploaded).  When calling from script, you can also provide an optional ' +
                    'parameter to control which files to include/exclude.',
    'epilog': '''examples:
  %(prog)s c:\\path\\to\\create\\asset\\collection\\from
'''
}

def fill_parser(p):
    p.add_argument('asset_collection_dir', help='The path to the directory to generate an asset collection from')
    p.add_argument('--name', '-n', default='', help='Name for the asset collection (default is the target directory name)')

##########################

def create_asset_collection(path_to_ac, ac_name, include=lambda fn, rp: fn not in ['idmtools.log', 'COMPS_log.log'] ):
    path_to_ac = os.path.normpath(path_to_ac)

    if not os.path.exists(path_to_ac) or not os.path.isdir(path_to_ac):
        raise RuntimeError('Path \'{0}\' doesn\'t exist or is not a directory'.format(path_to_ac))

    tags = {
        'Name': ac_name if ac_name else os.path.basename(path_to_ac)
    }

    ac = AssetCollection()
    ac.set_tags(tags)

    # First try creating it without uploading any files (just by md5sum)
    for (dirpath, dirnames, filenames) in os.walk(path_to_ac):
        for fn in filenames:
            rp = os.path.relpath(dirpath, path_to_ac) if dirpath != path_to_ac else ''

            if not include(fn, rp):
                continue

            logger.info('Adding {0}'.format(os.path.join(rp, fn)))

            with open(os.path.join(dirpath, fn), 'rb') as f:
                md5calc = md5()
                while True:
                    datachunk = f.read(8192)
                    if not datachunk:
                        break
                    md5calc.update(datachunk)
                md5_checksum_str = md5calc.hexdigest()

            acf = AssetCollectionFile(fn, rp, md5_checksum=md5_checksum_str, tags={'Executable':None} if os.path.splitext(fn)[1] == '.exe' else None)
            ac.add_asset(acf)

    missing_files = ac.save(return_missing_files=True)

    # If COMPS responds that we're missing some files, then try creating it again,
    # uploading only the files that COMPS doesn't already have.
    if missing_files:
        logger.info(f'Uploading {len(missing_files)} missing file{"s" if len(missing_files) > 1 else ""}')
        logger.debug('Missing files: [' + ','.join([ str(u) for u in missing_files]) + ']')

        ac2 = AssetCollection()
        ac2.set_tags(tags)

        for acf in ac.assets:
            if acf.md5_checksum in missing_files:
                rp = acf.relative_path
                fn = acf.file_name
                acf2 = AssetCollectionFile(fn, rp, tags=acf.tags)
                ac2.add_asset(acf2, os.path.join(path_to_ac, rp, fn))
            else:
                ac2.add_asset(acf)

        ac2.save()
        ac = ac2

        logger.info('')

    logger.info('Done - created AC ' + str(ac.id))

    return ac.id


def main(args):
    Client.login(args.comps_server)
    create_asset_collection(args.asset_collection_dir, args.name)
