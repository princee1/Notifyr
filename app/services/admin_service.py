from datetime import timedelta
from app.definition._service import BaseMiniService, BaseMiniServiceManager, BaseService, BuildFailureError, MiniService, Service, ServiceStatus
from app.errors.security_error import CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError,AlreadyBlacklistedClientError
from app.models.security_model import ChallengeORM, ClientORM, GroupClientORM, BlacklistORM
from app.services.database_service import TortoiseConnectionService
from app.services.security_service import JWTAuthService


@MiniService()
class ClientMiniService(BaseMiniService):
    ...

@Service()
class AdminService(BaseMiniServiceManager):

    def __init__(self,jwtAuthService:JWTAuthService,tortoiseConnService:TortoiseConnectionService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
        self.tortoiseConnService = tortoiseConnService

    def build(self,build_state=-1):
        ...
    
    def verify_dependency(self):
        if self.tortoiseConnService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError
    
    async def is_blacklisted(self, client: ClientORM) -> tuple[bool, float | None]:
        blacklist = await BlacklistORM.filter(client=client).first()
        if blacklist:
            time_left = (blacklist.expired_at - blacklist.created_at).total_seconds()
            return True, time_left

        if client.group_id is None:
            return False, None

        group_blacklist = await BlacklistORM.filter(group=client.group_id).first()
        if group_blacklist:
            time_left = (group_blacklist.expired_at - group_blacklist.created_at).total_seconds()
            return True, time_left

        return False, None
        
    async def blacklist(self,client: ClientORM,group:GroupClientORM,time:float):

        if client!=None and group == None:
            is_blacklist,_ = await self.is_blacklisted(client)
            if is_blacklist:
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
            is_blacklist,_ = await self.is_blacklisted(client)
            if not is_blacklist:
                raise AlreadyBlacklistedClientError(True)
            else:
                return await BlacklistORM.filter(client=client).delete()
        
        if not await BlacklistORM.exists(group=group):
            raise GroupAlreadyBlacklistedError(group.group_id,group.group_name,True)

        return await BlacklistORM.filter(group=group).delete()

    def issue_auth(self,challenge:ChallengeORM,client:ClientORM):

        group_id = None if not client.group_id else str(client.group_id)
        refresh_token = self.jwtAuthService.encode_refresh_token(client_id=str(client.client_id),challenge=challenge.challenge_refresh, group_id=group_id)

        if refresh_token == None:
            raise CouldNotCreateRefreshTokenError()

        auth_token = self.jwtAuthService.encode_auth_token(str(challenge.last_authz_id),str(client.client_id),challenge.challenge_auth, group_id)

        if auth_token == None:
            raise CouldNotCreateAuthTokenError()
        
        return auth_token,refresh_token
