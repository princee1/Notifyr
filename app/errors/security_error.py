from typing import Literal

from app.classes.auth_permission import AuthType, ClientType
from app.definition._error import BaseError

class ClientDoesNotExistError(BaseError):
    def __init__(self,client_id:str):
        self.client_id = client_id

class GroupDoesNotExistError(BaseError):
    def __init__(self, group_id:str):
        super().__init__(group_id)
        self.group_id = group_id

class CouldNotCreateRefreshTokenError(BaseError):
    def __init__(self) -> None:
        super().__init__('Could not create refresh token')

class CouldNotCreateAuthTokenError(BaseError):
    def __init__(self) -> None:
        super().__init__('Could not create auth token')

class SecurityIdentityNotResolvedError(BaseError):
    
    def __init__(self, token:str,reason:str):
        self.reason = token
        self.reason = reason

class GroupIdNotMatchError(BaseError):
    def __init__(self, client_group_id, group_id):
        self.client_group_id = client_group_id
        self.group_id = group_id
        super().__init__()

class IdentityAlreadyBlacklistedError(BaseError):

    def __init__(self,identity:str,mode:Literal['client','group','token'], reversed_=False):
        self.reversed_ = reversed_
        super().__init__()
        self.identity = identity
        self.mode = mode

class ClientTokenHeaderNotProvidedError(BaseError):
    ...

class AuthzSignatureMisMatchError(BaseError):
    def __init__(self, client_id:str):
        super().__init__(client_id)
        self.client_id = client_id

class PasswordLessAuthTypeStrategyError(BaseError):
    def __init__(self,client_type:ClientType,auth_type:AuthType,reason:str):
        super().__init__()
        self.reason = reason
        self.client_type = client_type
        self.auth_type = auth_type

class ProvidedHashNotEquivalentError(BaseError):
    def __init__(self, source_id:str,source_mode:str):
        super().__init__(source_id)
        self.source_id = source_id
        self.source_mode = source_mode

class IdentityBlacklistedError(BaseError):
    def __init__(self, identity:str, identity_type:str):
        super().__init__(identity)
        self.identity = identity
        self.identity_type = identity_type

class ClientAuthenticationFlagError(BaseError):

    def __init__(self, client_id:str,auth_flag_found:bool):
        super().__init__(client_id,auth_flag_found)
        self.client_id = client_id
        self.auth_flag_found = auth_flag_found
        self.flag_auth_expected = not auth_flag_found
