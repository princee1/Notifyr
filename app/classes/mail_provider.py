from dataclasses import dataclass
from msal import ConfidentialClientApplication
from typing import TypedDict
from utils.prettyprint import PrettyPrinter
from requests import post,get, Request,Response


@dataclass
class AccessToken(TypedDict):
    ...


class EmailProvider:
    def __init__(self,client_id:str,client_secret:str):
        self.client_id = client_id
        self.client_secret = client_secret
    
    def start_oauthflow(self):
        ...

    def grant_access_token(self):
        ...
    
    def encode_token(self):
        ...
    
    def get_auth_code(self):
        ...
    
    def refresh_access_token(self):
        ...

    @property
    def refresh_token(self):
        ...

    @property
    def access_token(self):
        ...

class Outlook(EmailProvider):
    ...

class Gmail(EmailProvider):
    ...

class ICloud(EmailProvider):
    ...

class YahooFamily(EmailProvider):
    '''
    Yahoo and Aol
    '''
    ...
