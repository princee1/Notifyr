from typing import Literal

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