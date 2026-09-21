from typing import Any, Literal

from app.classes.auth_permission import AuthType, ClientType
from app.definition._error import BaseError


class SecurityBaseError(BaseError):
    def __init__(self, message: str | None = None, **context: Any):
        self.message = message or self.__class__.__name__
        self.context = context
        super().__init__(self.message)

    @property
    def detail(self):
        return {"message": self.message, "details": self.context}


class ClientDoesNotExistError(SecurityBaseError):
    def __init__(self, client_id: str, from_auth: bool = False):
        self.client_id = client_id
        self.from_auth = from_auth
        super().__init__("Client does not exist", client_id=client_id, from_auth=from_auth)


class ClientAlreadyExistError(SecurityBaseError):
    def __init__(self, client_id: str | None = None):
        self.client_id = client_id
        super().__init__("Client already exists", client_id=client_id)


class GroupDoesNotExistError(SecurityBaseError):
    def __init__(self, group_id: str):
        self.group_id = group_id
        super().__init__("Group does not exist", group_id=group_id)


class CouldNotCreateRefreshTokenError(SecurityBaseError):
    def __init__(self, reason: str | None = None):
        self.reason = reason
        super().__init__("Could not create refresh token", reason=reason)


class CouldNotCreateAuthTokenError(SecurityBaseError):
    def __init__(self, reason: str | None = None):
        self.reason = reason
        super().__init__("Could not create auth token", reason=reason)


class SecurityIdentityNotResolvedError(SecurityBaseError):
    def __init__(self, token: str, reason: str):
        self.token = token
        self.reason = reason
        super().__init__("Security identity could not be resolved", reason=reason)


class GroupIdNotMatchError(SecurityBaseError):
    def __init__(self, client_group_id, group_id):
        self.client_group_id = client_group_id
        self.group_id = group_id
        super().__init__("Group id does not match", client_group_id=client_group_id, group_id=group_id)


class IdentityAlreadyBlacklistedError(SecurityBaseError):
    def __init__(self, identity: str, mode: Literal['client', 'group', 'session'], reversed_: bool = False):
        self.identity = identity
        self.mode = mode
        self.reversed_ = reversed_
        super().__init__("Identity is already blacklisted", identity=identity, mode=mode, reversed_=reversed_)


class ClientTokenHeaderNotProvidedError(SecurityBaseError):
    def __init__(self, header_name: str = 'Authorization'):
        self.header_name = header_name
        super().__init__("Client token header not provided", header_name=header_name)


class AuthzSignatureMisMatchError(SecurityBaseError):
    def __init__(self, client_id: str):
        self.client_id = client_id
        super().__init__("Authorization signature mismatch", client_id=client_id)


class PasswordLessAuthTypeStrategyError(SecurityBaseError):
    def __init__(self, client_type: ClientType, auth_type: AuthType, reason: str):
        self.client_type = client_type
        self.auth_type = auth_type
        self.reason = reason
        super().__init__("Passwordless auth strategy not allowed", client_type=str(client_type), auth_type=str(auth_type), reason=reason)


class JWTInvalidTokenError(SecurityBaseError):
    def __init__(self, token: str | None = None, reason: str | None = None):
        self.token = token
        self.reason = reason
        super().__init__("Invalid token", reason=reason)


class TokenExpiredError(SecurityBaseError):
    def __init__(self, token: str | None = None, token_type: str = 'token', reason: str | None = None):
        self.token = token
        self.token_type = token_type
        self.reason = reason
        super().__init__("Token expired", token_type=token_type, reason=reason)


class TokenGenerationMismatchError(SecurityBaseError):
    def __init__(self, expected_generation_id: str | None = None, actual_generation_id: str | None = None, token_type: str = 'token'):
        self.expected_generation_id = expected_generation_id
        self.actual_generation_id = actual_generation_id
        self.token_type = token_type
        super().__init__("Token generation id mismatch", expected_generation_id=expected_generation_id, actual_generation_id=actual_generation_id, token_type=token_type)


class TokenDataMissingError(SecurityBaseError):
    def __init__(self, missing_fields: list[str] | tuple[str, ...] | None = None, token: str | None = None):
        self.missing_fields = list(missing_fields or [])
        self.token = token
        super().__init__("Token data is missing required fields", missing_fields=self.missing_fields)


class APIKeyMissingError(SecurityBaseError):
    def __init__(self, source: str = 'api_key'):
        self.source = source
        super().__init__("API key is missing", source=source)

class APIKeyMismatchError(SecurityBaseError):
    def __init__(self, source: str = 'api_key', provided: str | None = None):
        self.source = source
        self.provided = provided
        super().__init__("API key provided does not match", source=source, provided=provided)


class ProvidedHashNotEquivalentError(SecurityBaseError):
    def __init__(self, source_id: str | None = None, source_mode: str | None = None):
        self.source_id = source_id
        self.source_mode = source_mode
        super().__init__("Provided hash does not match the stored value", source_id=source_id, source_mode=source_mode)


class IdentityBlacklistedError(SecurityBaseError):
    def __init__(self, identity: str, identity_type: str):
        self.identity = identity
        self.identity_type = identity_type
        super().__init__("Identity is blacklisted", identity=identity, identity_type=identity_type)


class ClientAuthenticationFlagError(SecurityBaseError):
    def __init__(self, client_id: str, auth_flag_found: bool):
        self.client_id = client_id
        self.auth_flag_found = auth_flag_found
        self.flag_auth_expected = not auth_flag_found
        super().__init__("Client authentication flag mismatch", client_id=client_id, auth_flag_found=auth_flag_found, flag_auth_expected=self.flag_auth_expected)

class SessionNotValidatedError(SecurityBaseError):

    def __init__(self,client_id:str,session:str):
        self.client_id = client_id 
        self.session = session
        super().__init__('Session Could not be validated',client_id=client_id,session_provided=session)

