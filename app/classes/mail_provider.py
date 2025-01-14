from dataclasses import dataclass
from msal import ConfidentialClientApplication
from typing import TypedDict, overload
from utils.prettyprint import PrettyPrinter
from requests import post,get, Request,Response
import json
from utils.helper import b64_encode
from typing import Literal
from enum import Enum


GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'
GOOGLE_REDIRECT_URI = 'https://oauth2.dance/'


GrantType = Literal['authorization_code','refresh_token']


@dataclass
class AccessToken(TypedDict):
    ...


class OAuth:

    @overload
    def __init__(self,client_id:str,client_secret:str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens:AccessToken | None = ... 

    @overload
    def __init__(self,json_key):
        self.json_key_file = json_key
        self.tokens:AccessToken | None = ... 



class OauthFlow(OAuth):
    def __init__(self,client_id:str,client_secret:str):
        super().__init__(client_id,client_secret)
        self.headers = {}
    
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


class OutlookOauth(OauthFlow):
    ...

class GmailOauth(OauthFlow):
    ...

class GoogleServiceOauth(OauthFlow):
    ...

class ICloud(OauthFlow):
    ...

class YahooFamilyOauth(OauthFlow):
    '''
    Yahoo and Aol
    '''
    ...


class GoogleLibFlow(OAuth):
    ...

class MailAPI:
    ...
