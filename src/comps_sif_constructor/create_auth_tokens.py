"""
This file is used to create a static credential prompt for the COMPS client.
https://github.com/EMOD-Hub/emodpy-malaria/blob/main/tests/create_auth_token_args.py
"""
from COMPS.CredentialPrompt import CredentialPrompt

class StaticCredentialPrompt(CredentialPrompt):
    def __init__(self, comps_url, username, password):
        if (comps_url is None) or (username is None) or (password is None):
            print("Usage: python create_auth_token_args.py --comps_url url --username username --password pwd")
            print("\n")
            raise RuntimeError('Missing comps_url, or username or password')    
        self._times_prompted = 0
        self.comps_url = comps_url
        self.username = username
        self.password = password

    def prompt(self):
        print("logging in with hardcoded user/pw")
        self._times_prompted = self._times_prompted + 1
        if self._times_prompted > 3:
            raise RuntimeError('Failure authenticating')
        print("Hit here")
        return {'Username': self.username, 'Password': self.password}