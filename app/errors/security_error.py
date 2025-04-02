from app.definition._error import BaseError


class ClientDoesNotExistError(BaseError):
    ...

class GroupAlreadyBlacklistedError(BaseError):
    def __init__(self, group_id,group_name,reversed_ =False) -> None:
        self.group_id = group_id
        self.group_name = group_name
        self.reversed = reversed_
        super().__init__(f'Group {group_id} is already blacklisted')

class CouldNotCreateRefreshTokenError(BaseError):
    def __init__(self) -> None:
        super().__init__('Could not create refresh token')

class CouldNotCreateAuthTokenError(BaseError):
    def __init__(self) -> None:
        super().__init__('Could not create auth token')


class SecurityIdentityNotResolvedError(BaseError):
    
    def __init__(self, *args):
        super().__init__('Both group and client cant be None')


class GroupIdNotMatchError(BaseError):

    def __init__(self, client_group_id, group_id):
        self.client_group_id = client_group_id
        self.group_id = group_id
        super().__init__()


class AlreadyBlacklistedClientError(BaseError):

    def __init__(self, reversed_=False):
        self.reversed_ = reversed_
        super().__init__()

class ClientTokenHeaderNotProvidedError(BaseError):
    ...


class AuthzIdMisMatchError(BaseError):
    ...