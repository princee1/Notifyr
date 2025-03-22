from app.definition._service import Service, ServiceClass
from app.errors.security_error import CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError,BlacklistedClientError
from app.models.security_model import ClientORM, GroupClientORM, BlacklistORM
from app.services.security_service import JWTAuthService


@ServiceClass
class AdminService(Service):

    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService

    def build(self):
        ...
    
    async def is_blacklisted(client:ClientORM):
        if await BlacklistORM.exists(client=client):
            return True
        
        if client.group_id == None:
            return False

        return await BlacklistORM.exists(group=client.group_id)
        

    async def blacklist(self,client: ClientORM,group:GroupClientORM):

        if client!=None and group == None:
            if await self.is_blacklisted(client):
                raise BlacklistedClientError()
            else:
                return await BlacklistORM.create(client=client)
        
        if await BlacklistORM.exists(group=group):
            raise GroupAlreadyBlacklistedError(group_id=group.group_id,group_name=group.group_name)

        return await BlacklistORM.create(group=group)
    

    async def un_blacklist(self,client:ClientORM,group:GroupClientORM):
        if client!=None and group == None:
            if not await  self.is_blacklisted(client):
                raise BlacklistedClientError(True)
            else:
                return await BlacklistORM.filter(client=client).delete()
        
        if not await BlacklistORM.exists(group=group):
            raise GroupAlreadyBlacklistedError(group.group_id,group.group_name,True)

        return await BlacklistORM.filter(group=group).delete()

    
    def issue_auth(self,challenge,client,authModel):
        refresh_token = self.jwtAuthService.encode_refresh_token(challenge=challenge.challenge_refresh, issued_for=client.issued_for, group_id=client.group_id)

        if refresh_token == None:
            raise CouldNotCreateRefreshTokenError()

        auth_token = self.jwtAuthService.encode_auth_token(authModel.scope.value,
            authModel.allowed_routes, challenge.challenge_auth, authModel.roles, client.group_id,  client.issued_for, client.client_name, authModel.allowed_assets)

        if auth_token == None:
            raise CouldNotCreateAuthTokenError()
        
        return auth_token,refresh_token
