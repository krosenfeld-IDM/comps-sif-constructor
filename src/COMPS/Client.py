import os
import json
import logging
import re
import requests
try:
    from js import XMLHttpRequest, Blob, URLSearchParams, FormData
except ImportError:
    XMLHttpRequest = None
import time
import traceback
import urllib3
import COMPS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class Client(object):
    """
    Client object for managing access to COMPS
    """
    __auth_manager = None

    def __init__(self):
        pass

    @classmethod
    def auth_manager(cls):
        """
        Retrieve the AuthManager.

        Must be logged in first in, otherwise this raises a RuntimeError.

        :return: the AuthManager instance
        """
        if not cls.__auth_manager:
            raise RuntimeError('login() is required.')
        return cls.__auth_manager

    @classmethod
    def login(cls, hoststring, credential_prompt=None):
        """
        Log in to the COMPS service.

        The specified COMPS hoststring allows a couple points of flexibility:

        * Secure vs. Unsecure - Specifying the protocol as http or https allows the user to control
          whether the SSL transport is used for requests.  By default, https is used.
        * Port - Specifying a particular port allows the user to control the port to communicate
          over for requests.  By default, the standard port for the chosen protocol is used
          (i.e. 80 for http, 443 for https).

        For example, the following are all valid formats:

        * comps.idmod.org - uses secure https protocol over port 443.
        * http://internal.idmod.org - uses unsecure http protocol over port 80.
        * localhost:54321 - uses secure https protocol over port 54321.

        Calling login() when already logged into a different host is invalid and will raise a RuntimeError.  When
        already logged into the same host, nothing is done and the function returns immediately.

        :param hoststring: the COMPS host to connect to
        :param credential_prompt: a CredentialPrompt object that controls how the user will supply their login \
        credentials.  By default, pyCOMPS will try to open a graphical prompt (TKCredentialPrompt) and fall back \
        to console (ConsoleCredentialPrompt) if that fails.
        """
        if not hoststring:
            raise RuntimeError('COMPS host required for login')

        tmphoststring = hoststring.rstrip('/')

        match_obj = re.match(r'(?:(https?)(?:://))?([\w\.-]*)(?:(?::)(\d+))?$', tmphoststring)

        if match_obj is None:
            raise RuntimeError('Invalid format for host string: "{0}".  See help for correct usage.'.format(hoststring))

        logger.debug('Parsed login host: {0}'.format(match_obj.groups()))

        protocol = match_obj.group(1)
        host_name = match_obj.group(2)
        port = match_obj.group(3)

        tmphoststring = '{0}://{1}{2}'.format(
                                                protocol if protocol else 'https',
                                                host_name,
                                                ':{0}'.format(str(port)) if port else ''
                                             )

        if cls.__auth_manager is not None:
            oldhoststring = cls.__auth_manager.hoststring

            if oldhoststring != (os.environ.get('COMPS_SERVER') or tmphoststring).rstrip('/'):
                raise RuntimeError('Already logged into host \'{0}\'.  Must logout before logging into a different host.'.format(oldhoststring))

            if cls.__auth_manager.has_auth_token():
                logger.info('Already logged into {0}.  Skipping login.'.format(oldhoststring))
                return
        else:
            cls.__auth_manager = COMPS.AuthManager(tmphoststring, credential_prompt=credential_prompt)

        try:
            cls.__auth_manager.get_auth_token()   # force credentials prompt and caching of auth token
        except:
            cls.__auth_manager = None
            raise

    @classmethod
    def logout(cls, hoststring = None):
        """
        Log out of the COMPS service.

        If logged in, this clears any cached credentials and nulls the AuthManager instance.  Otherwise, you
        may pass a hoststring parameter to clear cached credentials for a particular COMPS host.

        :param hoststring: the COMPS host to clear credentials for

        """
        if hoststring is not None:
            tmp_authmgr = COMPS.AuthManager(hoststring)

            # If we're not already logged into the endpoint the user specified, then we're not really "logging
            # out", just clearing cached credentials
            if cls.__auth_manager is None or tmp_authmgr.hoststring != cls.__auth_manager.hoststring:
                logger.info('Clearing cached credentials for {}'.format(hoststring))
                tmp_authmgr.clear_auth_token()
                return

            # Otherwise, the hoststring is basically redundant, so just fall through...

        if cls.__auth_manager is not None:
            logger.info('Logging out of {}'.format(cls.__auth_manager.hoststring))
            cls.__auth_manager.clear_auth_token()
            cls.__auth_manager = None

    @classmethod
    def post(cls, path, include_comps_auth_token=True, http_err_handle_exceptions=None, **kwargs):
        return cls.request('POST', path, include_comps_auth_token, http_err_handle_exceptions or [], **kwargs)

    @classmethod
    def put(cls, path, include_comps_auth_token=True, http_err_handle_exceptions=None, **kwargs):
        return cls.request('PUT', path, include_comps_auth_token, http_err_handle_exceptions or [], **kwargs)

    @classmethod
    def get(cls, path, include_comps_auth_token=True, http_err_handle_exceptions=None, **kwargs):
        return cls.request('GET', path, include_comps_auth_token, http_err_handle_exceptions or [], **kwargs)

    @classmethod
    def delete(cls, path, include_comps_auth_token=True, http_err_handle_exceptions=None, **kwargs):
        return cls.request('DELETE', path, include_comps_auth_token, http_err_handle_exceptions or [], **kwargs)

    @classmethod
    def request(cls, method, path, include_comps_auth_token=True, http_err_handle_exceptions=None, **kwargs):
        http_err_handle_exceptions = http_err_handle_exceptions or []

        if 'headers' not in kwargs:
            kwargs['headers'] = {}

        if include_comps_auth_token:
            authtoken = cls.auth_manager().get_auth_token()
            kwargs['headers'][authtoken[0]] = authtoken[1]

        kwargs['headers']['Accept'] = 'application/json'
        if not kwargs.get('files') and 'Content-Type' not in kwargs['headers']:
            kwargs['headers']['Content-Type'] = 'application/json'

        max_tries = 10
        retry_delay_ms = 100

        req_url = cls.__build_url(path, method, kwargs.get('params'))

        for i in range(1, max_tries + 1):
            try:
                if XMLHttpRequest is None:  # normal python scenario
                    resp = requests.request(method,
                                            req_url,
                                            **kwargs)
                else:   # pyodide scenario
                    req = XMLHttpRequest.new()

                    if 'params' in kwargs:
                        req_url = req_url + "?" + URLSearchParams.new([ [k,str(kwargs['params'][k])] for k in kwargs['params'].keys() ]).toString()

                    req.open(method, req_url, False)

                    if 'headers' in kwargs:
                        for k,v in kwargs['headers'].items():
                            req.setRequestHeader(k, v)

                    if 'json' in kwargs:
                        req_body = Blob.new([json.dumps(kwargs['json'])], Client.__BlobPropertyBag('application/json'))
                    elif 'files' in kwargs:
                        req_body = FormData.new()
                        for f in kwargs['files']:
                            req_body.set(f[0], Blob.new([f[1][1]], Client.__BlobPropertyBag(f[1][2])), f[1][0])
                    elif 'data' in kwargs:
                        logger.info('Not Implemented!')
                        pass
                    else:
                        req_body = None

                    def callback(evt):
                        logger.info(req.readyState)
                        logger.info(req.status)
                        if req.readyState == XMLHttpRequest.DONE:
                            resp.status_code = req.status

                    #print(f'Body:\r' + str(req_body))
                    req.send(req_body)
                    resp = Client.__XmlHttpResponse(req)
                    #print(f'Response:\r' + str(resp))

                if i > 1:
                    logger.debug('Succeeded on attempt {0} of {1}'.format(str(i), str(max_tries)))

                break
            except Exception as e:
                logger.debug('Failed attempt {0} of {1}: {2}'.format(str(i), str(max_tries),
                                                                     traceback.format_exception_only(type(e), e)[0][:-1]))

                # It should always be safe to retry GET calls, but for PUT/POST/DELETE, retrying something that
                # already succeeded on the server-side could have unintended side-effects so we need to be more cautious
                if i < max_tries and (method == "GET" or cls.__should_retry(e)):
                    time.sleep(i * retry_delay_ms / 1000)
                    logger.debug('Retrying...')
                else:
                    logger.debug('NOT RETRYING')
                    logger.debug(type(e))
                    if hasattr(e.args[0], 'reason'):
                        logger.debug(type(e.args[0].reason))

                    raise

        if 400 <= resp.status_code < 600 and \
                    resp.status_code not in http_err_handle_exceptions:
            # there was an error, let's try to get a good error-message from the response
            cls.raise_err_from_resp(resp)

        return resp

    @classmethod
    def raise_err_from_resp(cls, resp):
        resp_msg = None

        try:
            json_resp = resp.json()
            resp_msg = json_resp['ResponseMessage']
            corr_id = json_resp.get('CorrelationId')
        except json.decoder.JSONDecodeError as e:
            logger.debug('Invalid response: {0}'.format(resp.content))
            logger.debug('Exception: {0}'.format(str(e)))
            # raise this exception below to stop exception chaining
        except Exception as e:
            # couldn't get a good error-message from the response, just log and then exception out
            logger.debug('Invalid response: {0}'.format(resp.content))
            logger.debug('Exception: {0}'.format(str(e)))

            resp.raise_for_status()

        if not resp_msg:
            resp.raise_for_status()

        raise RuntimeError('{0} {1} - {2}{3}'.format(str(resp.status_code),
                                                     resp.reason,
                                                     resp_msg,
                                                     ' (CorrelationId = {0})'.format(corr_id) if corr_id else ''))

    @classmethod
    def __build_url(cls, path, method, params):
        url = '{0}{1}/{2}'.format(cls.__auth_manager.hoststring,
                                  '/api' if not path.startswith('asset/') and not path.startswith('/asset/') else '',
                                  (path[1:] if path.startswith('/') else path))
        logger.debug('REQUEST -> {0} {1}{2}'.format(method, url, ' ' + str(params) if params else ''))

        return url

    @classmethod
    def __should_retry(cls, e):
        try:
            if isinstance(e, requests.exceptions.ChunkedEncodingError):
                return True
            elif isinstance(e, requests.exceptions.SSLError):
                return True
            elif isinstance(e, requests.exceptions.ConnectionError) and \
                    hasattr(e.args[0], 'reason') and \
                    ( isinstance(e.args[0].reason, urllib3.exceptions.NewConnectionError) or \
                      isinstance(e.args[0].reason, urllib3.exceptions.SSLError) or \
                      isinstance(e.args[0].reason, requests.exceptions.SSLError) or \
                      isinstance(e.args[0].reason, BrokenPipeError) ):
                return True
        except Exception:
            pass

        return False



    class __XmlHttpResponse(object):
        status_code = None
        content = None
        headers = None
        reason = None

        def __init__(self, req):
            self.content = req.response
            self.status_code = req.status
            self.reason = req.statusText
            self.headers = {} # TODO: fill this in

        def json(self):
            return json.loads(self.content)

    class __BlobPropertyBag:
        def __init__(self, type='', endings='transparent'):
            self.type = type
            self.endings = endings
