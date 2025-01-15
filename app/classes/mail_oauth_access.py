from dataclasses import dataclass
from msal import ConfidentialClientApplication
from typing import Any, Optional, Type, TypeVar, TypedDict, overload
from utils.fileIO import JSONFile
from utils.prettyprint import PrettyPrinter_
from requests import post, Request,Response
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from utils.helper import b64_encode
from typing import Literal,List, Optional
from enum import Enum
import time
import pickle
from utils.helper import format_url_params
from utils.constant import EmailHostConstant
from utils.dependencies import APIFilterInject

class OAuthError(Exception):
    """Base class for all OAuth-related errors."""
    pass


class GoogleOAuthError(OAuthError):
    """Base class for Google OAuth-specific errors."""
    pass

class InvalidAuthorizationCodeError(OAuthError):
    ...

class InvalidGrantError(OAuthError):
    """Raised when the grant (authorization code or refresh token) is invalid."""
    pass

class AdminPolicyEnforcedError(GoogleOAuthError):
    """Raised when access is restricted due to an admin policy."""
    pass

class TokenExpiredError(OAuthError):
    """Raised when the access or refresh token has expired."""
    pass

class RateLimitExceededError(OAuthError):
    """Raised when the rate limit for API requests is exceeded."""
    pass

class YahooOAuthError(OAuthError):
    """Base class for Yahoo OAuth-specific errors."""
    pass

class InvalidClientError(OAuthError):
    """Raised when client credentials are invalid."""
    pass

class AccessDeniedError(OAuthError):
    """Raised when access is denied by the user or admin."""
    pass




GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'
GOOGLE_REDIRECT_URI = 'https://oauth2.dance/'
YAHOO_BASE_URL = 'https://api.login.yahoo.com/oauth2'
AOL_BASE_URL = 'https://'

GMAIL_SCOPE = 'https://mail.google.com/'

OOB_STR = 'oob'

GrantType = Literal['authorization_code', 'refresh_token']
YahooFamily = Literal['YAHOO', 'AOL']
TokenType = Literal['bearer', 'basic']


@dataclass
class AuthToken(TypedDict):
    access_token: str
    refresh_token: str
    token_type: TokenType
    expires_in: float
    acquired_at: float
    scope: Optional[str] 


#########################################################                ##################################################
class OAuth:

    def __init__(self, client_id: str, client_secret: str, scope: list[str], baseurl: str,json_key =None,state:str |None =None ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.baseurl = baseurl
        self.state_ = state
        self.auth_tokens: AuthToken | None = ...
        self.temp_data: Any = None
        self.json_key_file = json_key

    def load_authToken(self,filepath:str):
        self.filepath=filepath
        self.token_jsonFile = JSONFile(self.filepath) # VERIFY Security Issues
        tokens = self.token_jsonFile.data
        
        if tokens != None and isinstance(tokens,dict):
            self.auth_tokens = AuthToken(**tokens)
            self.save()
        else:
            self.auth_tokens = AuthToken()
        return self.exists

    def save(self):
        self.token_jsonFile.load(self.auth_tokens)
        self.token_jsonFile.save()

    @property
    def state(self):
        return '' if self.state_ == None else f'&state{self.state_}'
    
    @property
    def is_valid(self):    
        return time.time() - self.auth_tokens['acquired_at'] < self.auth_tokens['expires_in']
    
    @property
    def exists(self):
        if self.auth_tokens == None or self.auth_tokens == {}:
            return False
        if 'access_token' not in self.auth_tokens:
            return False
        
        return True

    @property
    def refresh_token(self):
        if self.auth_tokens is None:
            return None
        return self.auth_tokens['refresh_token']

    @property
    def access_token(self):
        if self.auth_tokens is None:
            return None
        return self.auth_tokens['access_token']

    def __repr__(self):
        return '%s(client_id=%s, client_secret=%s)' % (self.__class__.__name__,self.client_id, self.client_secret)

    def grant_access_token(self):
        ...

    def refresh_access_token(self):
        ...
    
    def build_auth_string(self,username:str):
        return'user=%s\x01auth=Bearer %s\x01\x01' % (
            username, self.access_token)

    def encode_token(self, username, b64=True):
        auth_string = self.build_auth_string(username)
        if b64:
            auth_string = b64_encode(auth_string)
        return auth_string

    def update_tokens(self, data: dict):
        self.auth_tokens = AuthToken(**data,acquired_at=time.time())
        self.save()

#########################################################                ##################################################

class GoogleLibraryFlow(OAuth):
    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        scope: Optional[List[str]] = None,
        baseurl: Optional[str] = None,
        state: Optional[str] = None,
        json_key_file: Optional[str] = None,
    ):
        # Use either the client credentials or the JSON key file
        if json_key_file:
            self.json_key_file = json_key_file
            self.auth_tokens = None
        else:
            super().__init__(client_id, client_secret, scope, baseurl, state)

    def grant_access_token(self):
        if hasattr(self, 'json_key_file') and self.json_key_file:
            # Use JSON file for credentials
            flow = InstalledAppFlow.from_client_secrets_file(self.json_key_file, self.scope)
        else:
            # Use client_id and client_secret
            client_config = {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.baseurl],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, self.scope)

        credentials = flow.run_local_server(port=0)
        self.update_tokens({
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "expires_in": credentials.expiry.timestamp() - time.time(),
        })

    def update_tokens(self, data: dict):
        # Verify and store tokens
        if not all(key in data for key in ["access_token", "refresh_token", "expires_in"]):
            raise ValueError("Invalid token data")
        self.auth_tokens = AuthToken(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            acquired_at=time.time(),
        )

    def refresh_access_token(self):
        if not self.is_valid and self.refresh_token:
            creds = Credentials(
                token=self.auth_tokens.access_token,
                refresh_token=self.auth_tokens.refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_uri="https://oauth2.googleapis.com/token",
            )
            creds.refresh(Request())
            self.update_tokens({
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expires_in": creds.expiry.timestamp() - time.time(),
            })

class GoogleServiceOauth(OAuth):
    def __init__(self, json_key_file: str):
        """
        Initialize the service account with the JSON key file and scope.
        :param json_key_file: Path to the service account JSON key file.
        :param scope: List of scopes for the API access.
        """
        self.json_key_file = json_key_file
        self.scope = [] #TODO add scope
        self.credentials = None
        self.auth_tokens = None

    def grant_access_token(self):
        """
        Authenticate using the service account and generate an access token.
        """
        self.credentials = service_account.Credentials.from_service_account_file(
            self.json_key_file, scopes=self.scope
        )
        self.refresh_access_token()

    def refresh_access_token(self):
        """
        Refresh the access token using the service account credentials.
        """
        if self.credentials.expired or not self.credentials.valid:
            self.credentials.refresh(Request())
            self.update_tokens({
                "access_token": self.credentials.token,
                "expires_in": self.credentials.expiry.timestamp() - time.time(),
            })

    def update_tokens(self, data: dict):
        """
        Update the token storage with new access token data.
        """
        if "access_token" not in data or "expires_in" not in data:
            raise ValueError("Invalid token data")
        self.auth_tokens = AuthToken(
            access_token=data["access_token"],
            expires_in=data["expires_in"],
            acquired_at=time.time(),
        )

    @property
    def access_token(self):
        """
        Return the current access token. Refresh if necessary.
        """
        if self.auth_tokens and time.time() > self.auth_tokens.acquired_at + self.auth_tokens.expires_in:
            self.refresh_access_token()
        return self.auth_tokens.access_token

class OutlookOauth(OAuth):
    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        super().__init__(client_id, client_secret, '', '')#TODO add scope  # BUG add url 

        self.tenant_id = tenant_id
        self.authority = f'https://login.microsoftonline.com/{self.tenant_id}'
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )

    def grant_access_token(self):
        self.app.acquire_token_for_client(self.scope)

#########################################################                ##################################################

class OAuthFlow(OAuth):
    def __init__(self, client_id: str, client_secret: str, scope: list[str], base_url: str,state=None):
        super().__init__(client_id, client_secret, scope, base_url,state)
        self.authHeaders = {}
        self.authBody = {}
        self.authParams = {}
        self.prettyPrinter = PrettyPrinter_

    @property
    def access_token(self):
        if not self.is_valid:
            self.refresh_access_token()
        return self.auth_tokens['access_token']
    

    def get_auth_code(self, url: str, show_init_message=True):
        self.prettyPrinter.show(pause_after=0.2, print_stack=False)
        self.prettyPrinter.info(
            "Visit the url below, follow the instructions and enter the authorization code", show=show_init_message,saveable=False)
        self.prettyPrinter.custom_message(
            "%s" % url, emoji_code='\U0001F310', position='both',saveable=False)
        self.prettyPrinter.space_line(saveable=False)
        val = self.prettyPrinter.input(
            'Enter the authorization code: ', emoji_code='\U0001F510', position='left')
        if isinstance(val, str) and val:
            return val.strip()
        return None

    def request_tokens(self, route: str):
        url = f'{self.baseurl}/{route}'

        response = post(url, self.authBody,
                        headers=self.authHeaders, params=self.authParams)
        val = response.json()
        self.temp_data = val
        return self.update_tokens(val)

    def refresh_access_token(self):
        ...

    def get_access_token(self, auth_code: str):
        ...

    def grant_access_token(self):
        '''
        Raise SkipInputException 
        '''
        show_init_message = True
        while True:

            authorization_code = self.get_auth_code(show_init_message=show_init_message)
            if authorization_code == None:
                show_init_message = True
                self.prettyPrinter.error('No authorization code was provided')
                self.prettyPrinter.wait(2, False)
                continue

            flag_,mess = self.get_access_token(authorization_code)
            if not flag_:
                show_init_message = False
                self.prettyPrinter.error(f'Error getting access token: {mess}')
                self.prettyPrinter.wait(1.5, False)
                continue

            break
#########################################################                ##################################################

class GmailHTTPOAuth(OAuthFlow):

    def __init__(self, client_id, client_secret,):
        super().__init__(client_id, client_secret, GMAIL_SCOPE, GOOGLE_ACCOUNTS_BASE_URL)
        self.authParams['client_id'] = self.client_id
        self.authParams['client_secret'] = self.client_secret

    def get_auth_code(self,show_init_message):
        params = {}
        params['client_id'] = self.client_id
        params['redirect_uri'] = GOOGLE_REDIRECT_URI
        params['scope'] = self.scope
        params['response_type'] = 'code'
        params['access_type'] = 'offline'
        params['prompt'] = 'consent'
        url = f'{self.baseurl}/o/oauth2/auth?{format_url_params(params)}'
        return super().get_auth_code(url, show_init_message)

    def request_tokens(self,):
        return super().request_tokens('o/oauth2/token')

    def refresh_access_token(self):
        self.authParams['refresh_token'] = self.refresh_token
        self.authParams['grant_type'] = 'refresh_token'
        self.authParams.pop('code', None)
        self.authParams.pop('redirect_uri', None)
        self.request_tokens()

    def get_access_token(self, auth_code):
        self.authParams['code'] = auth_code
        self.authParams['redirect_uri'] = GOOGLE_REDIRECT_URI
        self.authParams['grant_type'] = 'authorization_code'
        self.authParams.pop('refresh_token', None)
        self.request_tokens()

    def update_tokens(self, data):

        if 'error' in data:
            error = data['error']
            if error == 'invalid_grant':
                raise InvalidGrantError("The refresh token is invalid or has been revoked.")
            elif error == 'admin_policy_enforced':
                raise AdminPolicyEnforcedError("Access restricted due to admin policy enforcement.")
            elif error == 'rate_limit_exceeded':
                raise RateLimitExceededError("Rate limit exceeded for Google API.")
            else:
                raise GoogleOAuthError(f"Unexpected Google OAuth error: {error}")

        return super().update_tokens(data)

class YahooFamilyOAuth(OAuthFlow):
    '''
    Yahoo and Aol
    '''

    def __init__(self, client_id: str, client_secret: str, yFamily: YahooFamily = 'YAHOO'):
        self.yFamily = yFamily
        baseurl = YAHOO_BASE_URL if yFamily == 'YAHOO' else AOL_BASE_URL
        super().__init__(client_id, client_secret, None, baseurl)
        self.authBody['redirect_uri'] = OOB_STR
        self.bearer = b64_encode(f'{client_id}:{client_secret}')
        self.authHeaders['Authorization'] = 'Basic ' + self.bearer
        self.authHeaders['Content-Type']= "application/x-www-form-urlencoded"

    def build_auth_string(self, username):
        return f"n,a={username},^Aauth=Bearer {self.access_token}^A^A"

    def update_tokens(self, tokens):
        
        if 'error' in tokens:
            error = tokens['error']
        
            if error == 'invalid_client':
                raise InvalidClientError("Invalid client credentials provided.")
            elif error == 'access_denied':
                raise AccessDeniedError("Access denied by user or admin.")
            elif error == 'unsupported_grant_type':
                raise InvalidGrantError("The grant type is not supported by Yahoo.")
            elif error == 'rate_limit_exceeded':
                raise RateLimitExceededError("Rate limit exceeded for Yahoo API.")
            elif error == 'INVALID_AUTHORIZATION_CODE':
                raise InvalidAuthorizationCodeError("Invalid authorization code")

            else:
                raise YahooOAuthError(f"Unexpected Yahoo OAuth error: {error}")
        return super().update_tokens(tokens)

    def get_auth_code(self,show_init_message):
        url = f'{self.baseurl}/request_auth?client_id={self.client_id}&redirect_uri={OOB_STR}&response_type=code&language=en-us{self.state}'
        return super().get_auth_code(url, show_init_message)

    def get_access_token(self, auth_code: str):
        try:
            self.authBody['grant_type'] = 'authorization_code'
            self.authBody['code'] = auth_code
            self.authBody.pop('refresh_token', None)
            self.request_tokens()
            return True,''
        except InvalidAuthorizationCodeError as e:
            return False,e.args[0]

        except InvalidGrantError as e:
            return False,e.args[0]
            
        return False,''

    def refresh_access_token(self):
        self.authBody['refresh_token'] = self.refresh_token
        self.authBody['grant_type'] = 'refresh_token'
        self.authBody.pop('code', None)
        self.request_tokens()

    def request_tokens(self, ):
        return super().request_tokens('get_token')


O = TypeVar('O', bound = OAuth)
#########################################################                #################################################
# class GoogleServiceJWT:
#     ...
#########################################################                #################################################
GoogleFlowType = Literal['service_account','oauth_custom','oauth_automatic']

#########################################################                #################################################


class MailOAuthFactoryError(Exception):
    ...

def MailOAuthFactory(emailHost:EmailHostConstant,kwargs:dict[str,Any],google_oauth_flow:Literal[GoogleFlowType]=None,json_file:str =None)->OAuth | OAuthFlow:
    match emailHost:
        case EmailHostConstant.AOL:
            kwargs['yFamily'] = 'AOL'
            return APIFilterInject(YahooFamilyOAuth)(**kwargs)
        case EmailHostConstant.YAHOO:
            kwargs['yFamily'] = 'YAHOO'
            return APIFilterInject(YahooFamilyOAuth)(**kwargs)
        case EmailHostConstant.OUTLOOK:
            return APIFilterInject(OutlookOauth)(**kwargs)
        
        case (EmailHostConstant.GMAIL, EmailHostConstant.GMAIL_RELAY, EmailHostConstant.GMAIL_RESTRICTED):
            if google_oauth_flow =='service_account':
                return GoogleServiceOauth(json_key_file=json_file)
            elif google_oauth_flow =='oauth_automatic':
                if json_file ==  None:
                    return APIFilterInject(GoogleLibraryFlow)(**kwargs) # Might give error
                else:
                    return GoogleLibraryFlow(json_key_file=json_file)
            else:
                if 'client_id' not in kwargs and 'client_secret' not in kwargs:
                    raise MailOAuthFactoryError
                
                return APIFilterInject(GmailHTTPOAuth)(**kwargs)
        case _:
            
            raise MailOAuthFactoryError
    ...
    