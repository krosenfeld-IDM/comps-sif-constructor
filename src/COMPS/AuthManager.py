import os
import base64
import errno
import logging
import getpass
import tempfile
import xdg
from datetime import datetime, timedelta
from future.utils import raise_from

import COMPS
from COMPS.CredentialPrompt import get_credential_prompt, CredentialPrompt

logger = logging.getLogger(__name__)


class AuthManager(object):
    """
    Manage authentication to COMPS.
    """
    __comps_auth_token_key = 'X-COMPS-Token'
    __comps_client_version = 12
    __token_filename_format = 'COMPS_Authtoken_%s_%s.txt'
    __token_tokentype_index = 1
    __token_username_index = 2
    __token_expiration_index = 6
    __token_groups_index = 12
    __token_environments_index = 13
    __token_renewal_buffer = 120

    def __init__(self, hoststring, verify_certs=False, credential_prompt=None):
        self._hoststring = AuthManager.__normalize_hoststring(hoststring)

        override_hoststring = os.environ.get('COMPS_SERVER')

        if override_hoststring:
            override_hoststring = AuthManager.__normalize_hoststring(override_hoststring)

            if self._hoststring != override_hoststring:
                logger.info('Overriding hoststring with COMPS_SERVER environment variable')
                self._hoststring = override_hoststring

        self._verify_certs = verify_certs

        self._auth_token = None
        self._username = None
        self._group_list = None
        self._env_list = None
        self._token_expiration = datetime.min
        self._token_renewal_time = None

        if credential_prompt is None:
            # Using default credential prompt
            self._credential_prompt = get_credential_prompt()
        elif isinstance(credential_prompt, CredentialPrompt):
            # Using user-specified credential prompt
            self._credential_prompt = credential_prompt
        else:
            raise RuntimeError('Invalid credential_prompt; must pass object of type "CredentialPrompt".')

    @property
    def username(self):
        return self._username

    @property
    def hoststring(self):
        return self._hoststring

    @property
    def groups(self):
        return self._group_list

    @property
    def environments(self):
        return self._env_list

    def has_auth_token(self):
        return self._auth_token is not None

    def get_auth_token(self):
        now = datetime.utcnow()

        if (self._auth_token is None or      # <--- first time in this execution that we're getting an auth token
                now > self._token_renewal_time):  # <--- token is expired or near expiry, so check to see whether anyone else (e.g. another thread) has cached a newer token

            token_filename = self.__get_token_path()

            if os.path.exists(token_filename):
                with open(token_filename, 'r') as tf:
                    token_content = tf.readlines()
                    token = token_content[0] if token_content and token_content[0].strip() != '' else None

                if token:
                    self.__process_token(token)

        if now > self._token_expiration:
            self.__acquire_credentials()
        elif now > self._token_renewal_time:
            self.__renew_auth_token()

        return self.__comps_auth_token_key, self._auth_token

    def clear_auth_token(self):
        path = self.__get_token_path()

        # delete file if it exists
        try:
            os.remove(path)
        except OSError as e:
            if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
                logger.error('Error deleting cached credentials: {0}'.format(e.message))

        self._auth_token = None

    @staticmethod
    def get_environment_macros(environment_name):
        """
        Retrieve the environment macros for a COMPS environment.

        This may be a somewhat temporary requirement until the Asset Service handles
        file dependencies more completely (allows uploads, etc).

        :param environment_name: the COMPS environment to retrieve macros for
        :return: a dictionary of environment macro key/value pairs
        """
        path = '/Environments/{0}'.format(environment_name)
        resp = COMPS.Client.get(path)

        json_resp = resp.json()

        if 'Environments' not in json_resp or \
                len(json_resp['Environments']) != 1 or \
                'Macros' not in json_resp['Environments'][0]:
            logger.debug(json_resp)
            raise RuntimeError('Malformed Experiments retrieve response!')

        return json_resp['Environments'][0]['Macros']

    @staticmethod
    def get_group_name_for_environment(environment_name):
        """
        Retrieve the Group associated with a particular COMPS environment.

        :param environment_name: the COMPS environment to retrieve the Group for
        :return: a string of the Group name
        """
        path = '/Environments/{0}'.format(environment_name)
        resp = COMPS.Client.get(path)

        json_resp = resp.json()

        if 'Environments' not in json_resp or \
                len(json_resp['Environments']) != 1 or \
                'GroupName' not in json_resp['Environments'][0]:
            logger.debug(json_resp)
            raise RuntimeError('Malformed Experiments retrieve response!')

        return json_resp['Environments'][0]['GroupName']

    def __acquire_credentials(self):
        success = False

        logger.info('Logging into {0}'.format(self._hoststring))

        while not success:
            try:
                if '_prompt_user_for_creds' in dir(self):
                    print('WARNING!  This method of overriding the credentials input is deprecated.')
                    print('          Please check out the new "credential_prompt" argument on Client.login()')
                    creds = self._prompt_user_for_creds()
                else:
                    creds = self._credential_prompt.prompt()
            except:
                self._hoststring = None
                raise

            if creds is None:
                logger.info('User canceled login')
                self._hoststring = None
                break

            creds['ClientVersion'] = AuthManager.__comps_client_version

            creds['Password'] = base64.b64encode(creds['Password'].encode()).decode('utf-8')

            logger.debug('Sending auth request')

            resp = COMPS.Client.post("/tokens"
                                     , include_comps_auth_token=False
                                     , http_err_handle_exceptions=[302, 401]
                                     , allow_redirects=False
                                     , json=creds
                                     , verify=self._verify_certs)

            creds = None

            if resp.status_code == 302:
                raise RuntimeError('Error contacting login endpoint; attempting to hit \'http\' protocol instead of \'https\' ?')
            elif resp.status_code == 401:
                logger.info('Bad username/password')
                continue

            if AuthManager.__comps_auth_token_key in resp.headers:
                token = resp.headers[AuthManager.__comps_auth_token_key]
                self.__process_token(token)
                self.__cache_token(token)

                success = True
            else:
                logger.error('Error attempting to validate user credentials')

    def __renew_auth_token(self):
        success = False

        while not success:
            resp = COMPS.Client.put("/tokens"
                                    , include_comps_auth_token=False    # Don't try to get another auth token, otherwise we get in an
                                                                        #  endless loop... we will manually include the old one below...
                                    , json={ 'ClientVersion': AuthManager.__comps_client_version}
                                    , headers={ AuthManager.__comps_auth_token_key: self._auth_token }
                                    , verify=self._verify_certs)

            if AuthManager.__comps_auth_token_key in resp.headers:
                token = resp.headers[AuthManager.__comps_auth_token_key]
                self.__process_token(token)
                self.__cache_token(token)

                success = True
            else:
                logger.error('Error attempting to renew user credentials')

    def __process_token(self, token):
        tokensplit = token.split(',', AuthManager.__token_environments_index + 2) # 0-based + an extra so we separate from anything afterwards
        
        try:
            self._token_expiration = datetime.strptime(tokensplit[AuthManager.__token_expiration_index], '%Y-%m-%d-%H-%M-%S')
            self._group_list = tuple(tokensplit[AuthManager.__token_groups_index].split('-'))
            self._env_list = tuple(tokensplit[AuthManager.__token_environments_index].split('-'))

            # for when parsing cached token
            if self._username is None:
                self._username = tokensplit[AuthManager.__token_username_index]
        except (ValueError, IndexError) as e:
            raise_from(RuntimeError('Invalid auth token: {}'.format(self.__get_token_path())), None)

        tokentype = tokensplit[AuthManager.__token_tokentype_index]

        if tokentype == 'Auth':
            self._token_renewal_time = self._token_expiration - timedelta(minutes=AuthManager.__token_renewal_buffer)
        elif tokentype == 'System':
            self._token_renewal_time = self._token_expiration # system tokens can't be renewed anyway, so no point in trying to renew early
        else:
            raise RuntimeError('Unknown token type!')

        self._auth_token = token

    def __cache_token(self, token):
        path = self.__get_token_path()

        logger.debug('Caching auth token to ' + path)
        try:
            with open(path, 'w') as tf:
                tf.write(token)
        except ValueError as e:
            logger.error("Failure caching auth-token: {0}".format(e.message))

    def __get_token_path(self):
        hoststring_repl = ''.join([c if c not in ':/' else '_' for c in self._hoststring])

        tmppath = xdg.XDG_RUNTIME_DIR
        if not tmppath or not os.path.exists(tmppath):
            tmppath = tempfile.gettempdir()

        token_filename = os.path.join(tmppath,
                                      AuthManager.__token_filename_format % (hoststring_repl, getpass.getuser()))

        return token_filename

    @staticmethod
    def __normalize_hoststring(hoststring):
        hoststring_norm = hoststring.rstrip('/')

        if hoststring_norm.startswith('http:') and hoststring_norm.endswith(':80'):
            hoststring_norm = hoststring_norm[:-3]
        elif hoststring_norm.startswith('https:') and hoststring_norm.endswith(':443'):
            hoststring_norm = hoststring_norm[:-4]

        return hoststring_norm
