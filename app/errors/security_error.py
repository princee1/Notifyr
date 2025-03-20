from app.definition._error import BaseError

class GroupAlreadyBlacklistedError(BaseError):
    def __init__(self, group_id,group_name) -> None:
        self.group_id = group_id
        self.group_name = group_name
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
