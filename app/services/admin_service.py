from datetime import timedelta
from typing import TypedDict

from tortoise.expressions import Q
from app.classes.auth_permission import AuthPermission, PolicyModel, PolicyUpdateMode, Scope, filter_asset_permission, get_combined_policies, parse_authPermission_enum
from app.classes.secrets import ChaCha20SecretsWrapper
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, BuildFailureError, LinkDep, MiniService, Service, ServiceStatus
from app.errors.security_error import CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError,IdentityAlreadyBlacklistedError
from app.models.orm.security_model import ClientORM, GroupClientORM, PolicyMappingORM, UpdateClientModel
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import TortoiseConnectionService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.vault_service import VaultService
from app.utils.helper import generateId
from app.utils.toolbox import RunInThreadPool


class Credentials(TypedDict):
    password:str
    salt:str

class AuthSignature(TypedDict):
    signature:str

@MiniService()
class ClientMiniService(BaseMiniService):

    def __init__(self,vaultService:VaultService,configService:ConfigService,jwtService:JWTAuthService,securityService:SecurityService,client:ClientORM, policies:list[PolicyModel]=[],id=...):
        super().__init__(None, id)
        self.vaultService = vaultService
        self.configService = configService
        self.jwService = jwtService
        self.securityService = securityService
        self.client = client
        self.authPermission:AuthPermission = self.combine_policy(policies)

    def build(self, build_state = DEFAULT_BUILD_STATE):
        path = f"/{self.miniService_id}/auth-signature/"
        signature:AuthSignature = self.vaultService.secrets_engine.read('clients',path)
        self.signature = ChaCha20SecretsWrapper(signature)
        return super().build(build_state)

    @RunInThreadPool
    def encrypt_password(self,password:str):
        password,salt= self.securityService.hash(password,self.vaultService.CLIENT_PASSWORD_HASH_KEY)
        password = self.vaultService.transit_engine.encrypt(password,'security-key')
        salt = self.vaultService.transit_engine.encrypt(salt,'security-key')
        return password,salt
        
    @RunInThreadPool
    def store_password(self,password:str,salt:str):
        credentials = Credentials(password=password,salt=salt)
        path = f"{self.miniService_id}/credentials/"
        self.vaultService.security_engine.put('clients',credentials,path)

    @RunInThreadPool  
    def compare_password(self,provided_password:str):
        path = f"{self.miniService_id}/credentials/"
        credentials:Credentials=self.vaultService.security_engine.read('clients',path)
        salt:str = self.vaultService.transit_engine.decrypt(credentials['salt'],'security-key')
        password:str = self.vaultService.transit_engine.decrypt(credentials['password'],'security-key')
        self.securityService.compare_hash(password,provided_password,self.vaultService.CLIENT_PASSWORD_HASH_KEY,salt)
        return True

    @RunInThreadPool
    def create_auth_signature(self):
        signature ={'signature': generateId(20)}
        path = f"{self.miniService_id}/auth-signature"
        self.vaultService.security_engine.put('clients',signature,path)
        
    def compare_auth_signature(self,signature:str):
        authSignature:AuthSignature = self.signature.to_plain()
        if 'signature' not in authSignature:
            raise ...
        if signature != authSignature['signature']:
            raise ...

        return
        
    def verify_client_origin(self,origin:str):
        match self.client.scope:
            case Scope.SoloDolo:
                if origin != self.client.issued_for:
                    raise HTTPException( status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            case Scope.Organization:
                # TODO verify subnet
                    raise HTTPException( status_code=status.HTTP_403_FORBIDDEN, detail="Token not issued for this user")
            case Scope.Domain:
                if origin == None:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin header missing")
            case Scope.Free:
                ...

    def combine_policy(self,policies:list[PolicyModel])->AuthPermission:
        authPermission = get_combined_policies(policies)        
        filter_asset_permission(authPermission)
        parse_authPermission_enum(authPermission)
        return authPermission

    async def update_client(self, updateClient:UpdateClientModel,group:GroupClientORM|None,ctx=None):
        is_revoked=False
        if group==None:
            if updateClient.remove_group:
                self.client.group = None
                is_revoked = True
        else:
            self.client.group = group.group_id
            is_revoked = True

        if updateClient.password:
            password,salt = await self.encrypt_password(updateClient.password)
            await self.store_password(password,salt)

        if updateClient.client_description != None:
            self.client.client_description = updateClient.client_description

        if updateClient.client_name:
            self.client.client_name = updateClient.client_name
        
        if updateClient.client_scope and self.client.client_scope != updateClient.client_scope:
            self.client.client_scope = updateClient.client_scope
            is_revoked = True
        
        if updateClient.issued_for and self.client.issued_for != updateClient.issued_for:
            self.client.issued_for = updateClient.issued_for
            is_revoked = True

        await self.client.save(ctx)
        return is_revoked

    async def revoke_client(self,ctx=None,authenticated:bool=False,can_login:bool=False):
        await self.create_auth_signature()
        self.client.authenticated = authenticated
        if False:
            self.client.can_login = can_login
        await self.client.save(ctx)

    async def delete_itself(self,ctx=None):
        await self.client.delete(ctx)
        await RunInThreadPool(self.vaultService.security_engine.delete('clients',self.miniService_id))

    @property
    def client_id(self):
        return self.miniService_id

    @property
    def group_id(self):
        return None if self.client.group == None else str(self.client.group.group_id)

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

    async def update_policy(self, policy_ids: list[str], mode: PolicyUpdateMode, client:ClientMiniService  = None, group: GroupClientORM = None,ctx=None):
        # Get all current policy mappings for this client/group
        current_policies = PolicyMappingORM.filter(client=client.client, group=group)
        match mode:
            case 'delete':
                await current_policies.filter(Q(policy_id__in=policy_ids)).using_db(ctx).delete()
            case 'merge': # Add new policy_ids that are not already mapped
                current_policies = await current_policies
                new_policy_ids = set(policy_ids) - {pm.policy_id for pm in current_policies}
                await PolicyMappingORM.bulk_create([PolicyMappingORM(policy_id=pid, client=client.client, group=group)for pid in new_policy_ids],using_db=ctx)
            case 'set': # Remove all current mappings, then set only the provided policy_ids
                await current_policies.using_db(ctx).delete()
                await PolicyMappingORM.bulk_create([PolicyMappingORM(policy_id=pid, client=client.client, group=group)for pid in policy_ids],using_db=ctx)
            
    def verify_dependency(self):
        if self.tortoiseConnService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError('Could not retrieve security information')
        
        if self.redisService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError("Could not synchronize secruity updates")
    
    async def is_blacklisted(self, client: ClientORM,token:str=True) -> tuple[bool, float | None]:
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

    def issue_auth(self,client:ClientMiniService):


        refresh_token = self.jwtAuthService.encode_refresh_token()

        if refresh_token == None:
            raise CouldNotCreateRefreshTokenError()

        auth_token = self.jwtAuthService.encode_auth_token()

        if auth_token == None:
            raise CouldNotCreateAuthTokenError()
        
        return auth_token,refresh_token
