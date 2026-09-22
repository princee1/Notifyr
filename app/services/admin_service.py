from datetime import timedelta
import time
from typing import Literal, TypedDict

from tortoise.expressions import Q
from app.classes.auth_permission import AuthPermission, AuthSignature, AuthType, ClientRefresh, ClientType, Credentials, EncryptedRecoveryTokens, PolicyModel, PolicyUpdateMode, RecoveryTokens, Scope, filter_asset_permission, get_combined_policies, parse_authPermission_enum
from app.classes.secrets import ChaCha20SecretsWrapper
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseMiniServiceManager, BaseService, BuildFailureError, LinkDep, MiniService, Service, ServiceStatus
from app.errors.security_error import AuthzSignatureMisMatchError, CouldNotCreateAuthTokenError, CouldNotCreateRefreshTokenError,IdentityAlreadyBlacklistedError, MaximumSessionReachedError, PasswordLessAuthTypeStrategyError, ProvidedHashNotEquivalentError, SecurityIdentityNotResolvedError, SessionNotValidatedError
from app.models.orm.security_model import ClientORM, GroupClientORM, PolicyMappingORM, UpdateClientModel
from app.services.config_service import ConfigService
from app.services.database.redis_service import RedisService
from app.services.database.tortoise_service import SECURITY_CREDS, TortoiseConnectionService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.vault_service import VaultService
from app.utils.helper import generateId, uuid_v1_mc
from app.utils.toolbox import RunInThreadPool

class ClientVaultPath:

    @staticmethod
    def AUTH_SIGNATURE_PATH(client_id:str,session:str=''):
        if session:
            if not session.startswith('/'):
                session = f'/{session}'
        else:
            session=''
            
        return f'{client_id}/auth-signature{session}'

    @staticmethod
    def CREDENTIALS_PATH(client_id:str):
        return f'{client_id}/credentials'

    @staticmethod
    def RECOVERY_PATH(client_id:str):
        return f'{client_id}/recovery'

@MiniService()
class ClientMiniService(BaseMiniService):

    def __init__(self,vaultService:VaultService,configService:ConfigService,jwtService:JWTAuthService,securityService:SecurityService,client:ClientORM, policies:list[PolicyModel]=[]):
        self.client = client
        super().__init__(None, str(self.client.client_id))
        self.vaultService = vaultService
        self.configService = configService
        self.jwtService = jwtService
        self.securityService = securityService
        self.authPermission:AuthPermission = self.combine_policy(policies)

        self.sessions:dict[str,ChaCha20SecretsWrapper] = {}

    def build(self, build_state = DEFAULT_BUILD_STATE):
        path = ClientVaultPath.AUTH_SIGNATURE_PATH(self.miniService_id,'')
        sessions = self.vaultService.security_engine.list('clients',path)
        self.sessions.clear()
        for s in sessions:
            p = ClientVaultPath.AUTH_SIGNATURE_PATH(self.miniService_id,s)
            signature:AuthSignature = self.vaultService.security_engine.read('clients',p)
            self.sessions[p] = ChaCha20SecretsWrapper(signature)
        
    @RunInThreadPool
    def encrypt_password(self,password:str):
        password,salt= self.securityService.hash(password,self.vaultService.CLIENT_PASSWORD_HASH_KEY)
        password = self.vaultService.transit_engine.encrypt(password,'security-key')
        salt = self.vaultService.transit_engine.encrypt(salt,'security-key')
        return password,salt
        
    @RunInThreadPool
    def store_password(self,password:str,salt:str):
        credentials = Credentials(password=password,salt=salt)
        path = ClientVaultPath.CREDENTIALS_PATH(self.miniService_id)
        self.vaultService.security_engine.put('clients',credentials,path)

    @RunInThreadPool
    def fetch_password(self,):
        path = ClientVaultPath.CREDENTIALS_PATH(self.miniService_id)
        credentials:Credentials=self.vaultService.security_engine.read('clients',path)
        return credentials

    @RunInThreadPool  
    def compare_password(self,provided_password:str,credentials:Credentials):
        salt:str = self.vaultService.transit_engine.decrypt(credentials['salt'],'security-key')
        password:str = self.vaultService.transit_engine.decrypt(credentials['password'],'security-key')
        self.securityService.compare_hash(password,provided_password,self.vaultService.CLIENT_PASSWORD_HASH_KEY,salt)
        return True

    @RunInThreadPool
    def delete_session(self,session_id:str):
        path = ClientVaultPath.AUTH_SIGNATURE_PATH(self.client_id,session_id)
        self.vaultService.security_engine.delete('clients',path)

    @RunInThreadPool
    def upsert_session(self,session_id:str=None,ip:str=None,user_agent:str=None,_check_=True):
        authSignature = None
        if session_id and _check_:
            if not session_id in self.sessions:
                path = ClientVaultPath.AUTH_SIGNATURE_PATH(self.miniService_id,session_id)
                authSignature = self.vaultService.security_engine.read('clients',path)
            else:
                authSignature = self.sessions.get(session_id)
            authSignature['signature'] = generateId(20)

        else:
            session_id = str(uuid_v1_mc()) if session_id == None else session_id

        if authSignature == None:
            authSignature:AuthSignature = {}
            authSignature['ip'] = ip
            authSignature['signature'] = generateId(20)
            authSignature['time'] = time.time()
            authSignature['last_login'] = time.time()
            authSignature['user_agent'] = user_agent
        
        self.vaultService.security_engine.put('clients',authSignature,path)
        return authSignature

    @RunInThreadPool
    def create_recovery_code(self,recovery:EncryptedRecoveryTokens):
        path = ClientVaultPath.RECOVERY_PATH(self.client_id)
        self.vaultService.security_engine.put('clients',recovery,path)

    @RunInThreadPool
    def verify_login_count(self,session_id:str|None):
        if self.client.max_connection == None:
            return 

        path = f'clients/{ClientVaultPath.AUTH_SIGNATURE_PATH(self.client_id)}'
        sessions =  self.vaultService.security_engine.list(path)

        current_session_count = len(sessions)
        if session_id and session_id not in current_session_count:
            current_session_count+=1

        if current_session_count > self.client.max_connection:
            raise MaximumSessionReachedError(self.client_id,session_id,self.client.max_connection)
        
    def is_primary_session(self,session_id:str):
        return self.sessions.keys()[0] == session_id

    async def verify_recovery_code(self,code:str):
        path = ClientVaultPath.RECOVERY_PATH(self.client_id)
        recovery:EncryptedRecoveryTokens= await RunInThreadPool(self.vaultService.security_engine.read)('clients',path)
        tokens = recovery.get('tokens',[])

        if not tokens:
            raise ProvidedHashNotEquivalentError(code,'Recovery Code Setup')

        for token in tokens:
            try:
                await self.compare_password(code,token)
                return True
            except:
                continue
        
        raise ProvidedHashNotEquivalentError(code,'Recovery Code')

    def compare_auth_signature(self,signature:str,session:str=None,source:Literal['vault','memory']='memory'):

        if source == 'memory':
            if session not in self.sessions:
                raise SessionNotValidatedError(self.client_id,session)
        
            authSignature:AuthSignature = self.sessions[session].to_plain()

        else:
            path = f'clients/{ClientVaultPath.AUTH_SIGNATURE_PATH(self.client_id)}'
            sessions = self.vaultService.security_engine.list(path)

            if session not in sessions:
                raise SessionNotValidatedError(self.client_id,session)

            path = ClientVaultPath.AUTH_SIGNATURE_PATH(self.client_id,session)
            authSignature = self.vaultService.security_engine.read('clients',path)

        if 'signature' not in authSignature:
            raise AuthzSignatureMisMatchError(self.client_id)
        
        if signature != authSignature['signature']:
            raise AuthzSignatureMisMatchError(self.client_id)

        return
        
    def verify_client_origin(self,origin:str):
        return
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
        if not policies:
            return {}
        authPermission = get_combined_policies(policies)        
        filter_asset_permission(authPermission)
        parse_authPermission_enum(authPermission)
        return authPermission

    async def verify_refresh_token(self,refreshPermission:ClientRefresh):
        if refreshPermission['client_id'] != self.client_id:
            raise SecurityIdentityNotResolvedError(refreshPermission['client_id'],'Refresh Token client id mismatch')
        
        await RunInThreadPool(self.compare_auth_signature)(refreshPermission['auth_signature'],refreshPermission['session_id'],'vault')

    async def update_client(self, updateClient:UpdateClientModel,group:GroupClientORM|None,ctx=None):
        is_revoked=False
        password,salt = None,None
        if group==None:
            if updateClient.remove_group:
                self.client.group_id = None
                is_revoked = True
        else:
            self.client.group_id = group.group_id
            is_revoked = True
        
        if updateClient.client_username != None:
            self.client.client_username = updateClient.client_username

        if updateClient.password:
            if self.client.auth_type == AuthType.API_TOKEN:
                raise PasswordLessAuthTypeStrategyError(self.client.client_type,self.client.auth_type,"No password needed for 'API_TOKEN' authorization type")
            password,salt = await self.encrypt_password(updateClient.password)
            
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
        return is_revoked,password,salt

    async def revoke_itself(self,ctx=None,session_id:str='',can_login:bool|None=None,save=True):
        if can_login != None and self.client.auth_type == AuthType.ACCESS_TOKEN:
            self.client.can_login = can_login
        if save:
            await self.client.save(ctx)
        path = ClientVaultPath.AUTH_SIGNATURE_PATH(self.client_id,session_id)
        await RunInThreadPool(self.vaultService.security_engine.delete('clients',path))

    async def delete_itself(self,ctx=None):
        await self.client.delete(ctx)
        await RunInThreadPool(self.vaultService.security_engine.delete)('clients',self.miniService_id)

    async def generate_access(self,session:str,signature:str,refresh:bool=True,ctx=None,):
        refresh_token = None
        auth_token = self.jwtService.encode_auth_token(signature,session,self.client_id,self.client.auth_type)

        if auth_token == None:
            raise CouldNotCreateAuthTokenError()
        
        if refresh:
            refresh_token = self.jwtService.encode_refresh_token(signature,session,self.client_id)
            if refresh_token == None:
                raise CouldNotCreateRefreshTokenError()

        await self.client.save(ctx)
        return auth_token,refresh_token

    async def save(self,ctx):
        await self.client.save(ctx)

    @property
    def client_id(self):
        return self.miniService_id

    @property
    def group_id(self):
        return None if self.client.group is None else str(self.client.group.group_id)

SYNC_ADMIN_BUILD_STATE = 4234

@Service(is_manager=True,links=[
            LinkDep(VaultService),
            LinkDep(TortoiseConnectionService),
        ])
class AdminService(BaseMiniServiceManager[ClientMiniService]):

    def __init__(self,configService:ConfigService,jwtAuthService:JWTAuthService,tortoiseConnService:TortoiseConnectionService,vaultService:VaultService,redisService:RedisService,securityService:SecurityService):
        super().__init__()
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.tortoiseConnService = tortoiseConnService
        self.vaultService = vaultService
        self.redisService = redisService
        self.securityService = securityService

        self.policies:dict[str,PolicyModel] = {}
        self.mappings:list[dict] = []

    def build(self,build_state=DEFAULT_BUILD_STATE):

        if self.configService.AUTH_MECHANISM != 'userpass':
            return
        
        policies = {} 
        mappings = self.tortoiseConnService.fetch(PolicyMappingORM,listing='list')
        for pk in self.vaultService.security_engine.list('policies'):
            p = self.vaultService.security_engine.read('policies',pk)
            policies[pk] = PolicyModel(**p)

        self.policies= policies
        self.mappings = mappings

    async def load_clients(self,build_state=SYNC_ADMIN_BUILD_STATE):
        self.MiniServiceStore.clear()
        for client in await ClientORM.filter():
            policy = []
            for pmap in self.mappings:
                if client.client_id == pmap.get('client_id',None) or client.client_id == pmap.get('group_id',None):
                    policy.append(self.policies[pmap['policy_id']])
            service = ClientMiniService(self.vaultService,
                                        self.configService,
                                        self.jwtAuthService,
                                        self.securityService,
                                        client,policy)
            service._builder(BaseMiniService.QUIET_MINI_SERVICE,build_state,self.CONTAINER_LIFECYCLE_SCOPE)
            self.MiniServiceStore.add(service)

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

    async def disconnect_all(self,admin:bool=False,ctx=None):

        async for client in self.MiniServiceStore.aiter(predicate=lambda c:c.client.client_type!=ClientType.Admin or admin):
            async with self.tortoiseConnService.transaction(SECURITY_CREDS,silent=True) as ctx:
                await client.revoke_itself(ctx,can_login=True)
            
    @RunInThreadPool
    def revoke_all_tokens(self) -> None:
        new_generation_id = generateId(self.jwtAuthService.GENERATION_ID_LEN)
        self.vaultService.generation_engine.put('',{
            'GENERATION_ID':new_generation_id,
        },path=self.jwtAuthService.gen_id_path)
    
    @RunInThreadPool
    def unrevoke_all_tokens(self,version:int|None,destroy:bool,delete:bool,version_to_delete:list[int]=[]):
        self.vaultService.generation_engine.rollback('',self.jwtAuthService.gen_id_path,version,destroy,delete,version_to_delete)
