from datetime import timedelta
from app.definition._service import Service, ServiceClass
from app.errors.security_error import CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError,AlreadyBlacklistedClientError
from app.models.security_model import ChallengeORM, ClientORM, GroupClientORM, BlacklistORM
from app.services.security_service import JWTAuthService


@ServiceClass
class AdminService(Service):

    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService

    def build(self):
        ...
    
    async def is_blacklisted(self,client:ClientORM):
        if await BlacklistORM.exists(client=client):
            return True
        
        if client.group_id == None:
            return False

        return await BlacklistORM.exists(group=client.group_id)
        

    async def blacklist(self,client: ClientORM,group:GroupClientORM,time:float):

        if client!=None and group == None:
            if await self.is_blacklisted(client):
                raise AlreadyBlacklistedClientError()
            else:
                blacklist = await BlacklistORM.create(client=client)
                blacklist.expired_at = blacklist.created_at + timedelta(seconds=time)
                await blacklist.save()
                return blacklist
        
        if await BlacklistORM.exists(group=group):
            raise GroupAlreadyBlacklistedError(group_id=group.group_id,group_name=group.group_name)

        blacklist = await BlacklistORM.create(group=group)
        blacklist.expired_at = blacklist.created_at + timedelta(seconds=time)
        await blacklist.save()
        return blacklist


    

    async def un_blacklist(self,client:ClientORM,group:GroupClientORM):
        if client!=None and group == None:
            if not await self.is_blacklisted(client):
                raise AlreadyBlacklistedClientError(True)
            else:
                return await BlacklistORM.filter(client=client).delete()
        
        if not await BlacklistORM.exists(group=group):
            raise GroupAlreadyBlacklistedError(group.group_id,group.group_name,True)

        return await BlacklistORM.filter(group=group).delete()

    
    def issue_auth(self,challenge:ChallengeORM,client:ClientORM,authModel):
        refresh_token = self.jwtAuthService.encode_refresh_token(client_id=str(client.client_id),challenge=challenge.challenge_refresh, issued_for=client.issued_for, group_id=client.group_id,client_type=client.client_type)

        if refresh_token == None:
            raise CouldNotCreateRefreshTokenError()

        auth_token = self.jwtAuthService.encode_auth_token(client.client_type,str(client.client_id),authModel.scope.value,
            authModel.allowed_routes, challenge.challenge_auth, authModel.roles, client.group_id,  client.issued_for, client.client_name, authModel.allowed_assets)

        if auth_token == None:
            raise CouldNotCreateAuthTokenError()
        
        return auth_token,refresh_token
