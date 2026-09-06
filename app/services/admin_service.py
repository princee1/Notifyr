from datetime import timedelta
from app.classes.auth_permission import AuthPermission, PolicyModel, Scope, filter_asset_permission, get_combined_policies, parse_authPermission_enum
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, BuildFailureError, LinkDep, MiniService, Service, ServiceStatus
from app.errors.security_error import CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError, GroupAlreadyBlacklistedError,AlreadyBlacklistedClientError
from app.models.orm.security_model import ClientORM, GroupClientORM, PolicyMappingORM
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import TortoiseConnectionService
from app.services.security_service import JWTAuthService
from app.services.vault_service import VaultService
from app.utils.helper import generateId
from app.utils.toolbox import RunInThreadPool


@MiniService()
class ClientMiniService(BaseMiniService):

    def __init__(self,vaultService:VaultService,configService:ConfigService,jwtService:JWTAuthService,client:ClientORM, policies:list[PolicyModel]=[],id=...):
        super().__init__(None, id)
        self.vaultService = vaultService
        self.configService = configService
        self.jwService = jwtService
        self.client = client

        self.authPermission:AuthPermission = self.combine_policy(policies)

    def build(self, build_state = DEFAULT_BUILD_STATE):
        return super().build(build_state)

    @RunInThreadPool
    def encrypt_password(self,password:str):
        ...

    @RunInThreadPool
    def store_password(self,):
        ...

    def verify_client_origin(self,issued_for,origin=None):
        match self.authPermission['scope']:
            case Scope.SoloDolo:
                if issued_for != permission["issued_for"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            case Scope.Organization:
                # TODO verify subnet
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            case Scope.Domain:
                if origin == None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="Origin header missing")
            
            case Scope.Free:
                ...

    def combine_policy(self,policies:list[PolicyModel])->AuthPermission:
        authPermission = get_combined_policies(policies)        
        filter_asset_permission(authPermission)
        parse_authPermission_enum(authPermission)
        return authPermission

    async def _update_client(self, updateClient:UpdateClientModel, client:ClientORM, gid:str, authPermission,rm_group:bool):
            is_revoked=False
    
            if updateClient.group_id:
                group = await get_group(group_id=updateClient.group_id,gid=gid,authPermission=authPermission)
                client.group=group
                is_revoked = True
            else :
                if rm_group:
                    client.group = None
                    is_revoked = True
    
            if updateClient.password:
                password,salt = self.securityService.store_password(client.password,self.key)
                salt = str(salt)
                client.password = password
                client.password_salt= salt
                is_revoked = True
            
            if updateClient.client_description != None:
                client.client_description = updateClient.client_description
    
            if updateClient.client_name:
                client.client_name = updateClient.client_name
            
            if updateClient.client_scope and client.client_scope != updateClient.client_scope:
                client.client_scope = updateClient.client_scope
                is_revoked = True
            
            if updateClient.issued_for and client.issued_for != updateClient.issued_for:
                client.issued_for = updateClient.issued_for
                is_revoked = True
    
            else:
                if client.client_scope == Scope.SoloDolo:
                    if not ipv4_validator(client.issued_for):
                        raise ValueError(f"Invalid IPv4 address: {client.issued_for}")
                elif client.client_scope == Scope.Organization:
                    if not ipv4_subnet_validator(client.issued_for):
                        raise ValueError(f"Invalid IPv4 subnet: {client.issued_for}")
                    
            return is_revoked

    async def save(self):
        ...
@Service(is_manager=True,links=[
            LinkDep(VaultService),
            LinkDep(TortoiseConnectionService),
         ])
class AdminService(BaseMiniServiceManager[ClientMiniService]):

    def __init__(self,configService:ConfigService,jwtAuthService:JWTAuthService,tortoiseConnService:TortoiseConnectionService,vaultService:VaultService,redisService:RedisService):
        super().__init__()
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.tortoiseConnService = tortoiseConnService
        self.vaultService = vaultService
        self.redisService = redisService


    def build(self,build_state=DEFAULT_BUILD_STATE):
        policies = {}
        mapping = {}
        policies_keys=self.vaultService.security_engine.list('policies')
        for p in policies_keys:
            policies[p] = self.vaultService.security_engine.read('policies',p)

        for mapping in self.tortoiseConnService.vaultService(PolicyMappingORM):
            ...

        for client in self.tortoiseConnService.sync_find(ClientORM):
            print(client)

    async def _update_policy(self, policy_ids: list[str], mode: PolicyUpdateMode, client: ClientORM = None, group: GroupClientORM = None):
        # Get all current policy mappings for this client/group
        current_policies = PolicyMappingORM.filter(client=client, group=group)
        
        match mode:
            case 'delete':
                await current_policies.filter(Q(policy_id__in=policy_ids)).delete()

            case 'merge':
                # Add new policy_ids that are not already mapped
                current_policies = await current_policies
                current_policy_ids = {pm.policy_id for pm in current_policies}
                new_policy_ids = set(policy_ids) - current_policy_ids
                await PolicyMappingORM.bulk_create([
                    PolicyMappingORM(policy_id=pid, client=client, group=group)
                    for pid in new_policy_ids
                ])

            case 'set':
                # Remove all current mappings, then set only the provided policy_ids
                await current_policies.delete()
                await PolicyMappingORM.bulk_create([
                    PolicyMappingORM(policy_id=pid, client=client, group=group)
                    for pid in policy_ids
                ])
            
    def verify_dependency(self):
        if self.tortoiseConnService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError('Could not retrieve security information')
        
        if self.redisService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError("Could not synchronize secruity updates")
    
    async def is_blacklisted(self, client: ClientORM) -> tuple[bool, float | None]:
        ...
        
    async def blacklist(self,client: ClientORM,group:GroupClientORM,time:float):
        ...

    async def un_blacklist(self,client:ClientORM,group:GroupClientORM):
        ...

    @RunInThreadPool
    def revoke_all_tokens(self) -> None:
        new_generation_id = generateId(self.jwtAuthService.GENERATION_ID_LEN)
        self.vaultService.generation_engine.put('',{
            'GENERATION_ID':new_generation_id,
        },path=self.jwtAuthService.gen_id_path)
    
    @RunInThreadPool
    def unrevoke_all_tokens(self,version:int|None,destroy:bool,delete:bool,version_to_delete:list[int]=[]):
        self.vaultService.generation_engine.rollback('',self.jwtAuthService.gen_id_path,version,destroy,delete,version_to_delete)


    def issue_auth(self,challenge:ChallengeORM,client:ClientORM):

        group_id = None if not client.group_id else str(client.group_id)
        refresh_token = self.jwtAuthService.encode_refresh_token(client_id=str(client.client_id),challenge=challenge.challenge_refresh, group_id=group_id)

        if refresh_token == None:
            raise CouldNotCreateRefreshTokenError()

        auth_token = self.jwtAuthService.encode_auth_token(str(challenge.last_authz_id),str(client.client_id),challenge.challenge_auth, group_id)

        if auth_token == None:
            raise CouldNotCreateAuthTokenError()
        
        return auth_token,refresh_token
