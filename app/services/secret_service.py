import datetime
import time
from typing import Literal, TypedDict
import requests
from app.classes.secrets import ChaCha20SecretsWrapper
from app.classes.vault_engine import DatabaseVaultEngine, KV1VaultEngine, KV2VaultEngine, MinioS3VaultEngine, RabbitMQVaultEngine, TransitVaultEngine
from app.definition._service import DEFAULT_BUILD_STATE, DEFAULT_DESTROY_STATE, GUNICORN_BUILD_STATE, BaseService, BuildAbortError, Service, ServiceNotAvailableError, ServiceStatus, ServiceTemporaryNotAvailableError
from app.errors.service_error import BuildOkError
from app.interface.timers import IntervalInterface, IntervalParams, SchedulerInterface
from app.services.config_service import MODE, ConfigService, UvicornWorkerService
import hvac
from app.services.file_service import FileService
from app.utils.constant import VaultConstant, VaultTTLSyncConstant
from app.utils.fileIO import FDFlag
from datetime import datetime

from app.utils.helper import cron_interval, time_until_next_tick

DEFAULT_JWT_ALGORITHM = 'HS256'

class VaultTokenMeta(TypedDict):
    renewable: bool
    accessor: str
    creation_time: int
    creation_ttl: int
    expire_time: datetime
    explicit_max_ttl: int
    issue_time: datetime
    ttl: int

def parse_vault_token_meta(vault_lookup: dict) -> VaultTokenMeta:
    data = vault_lookup["data"]
    return {
        "renewable": data["renewable"],
        "accessor": data["accessor"],
        "creation_time": data["creation_time"],
        "creation_ttl": data["creation_ttl"],
        "expire_time": datetime.fromisoformat(data["expire_time"].replace("Z", "+00:00")),
        "explicit_max_ttl": data["explicit_max_ttl"],
        "issue_time": datetime.fromisoformat(data["issue_time"].replace("Z", "+00:00")),
        "ttl": data["ttl"],
    }


@Service()
class HCVaultService(BaseService,SchedulerInterface):

    _valid_role= {VaultConstant.MONGO_ROLE,VaultConstant.POSTGRES_ROLE}
    _secret_id_crontab='0 0 * * *'
    _ping_available_state = {ServiceStatus.AVAILABLE,ServiceStatus.PARTIALLY_AVAILABLE}
    
    def __init__(self,configService:ConfigService,fileService:FileService,uvicornWorkerService:UvicornWorkerService):
        super().__init__()
        self.configService = configService
        self.uvicornWorkerService = uvicornWorkerService
        self.fileService = fileService
        SchedulerInterface.__init__(self,replace_existing=True,thread_pool_count=1)
        self._jwt_algorithm = self.configService.getenv("JWT_ALGORITHM",DEFAULT_JWT_ALGORITHM)
        self.delay = IntervalParams(
            seconds=VaultTTLSyncConstant.SECRET_ID_ROTATION*.75
        )
        self.last_rotated = None

    @property
    def is_loggedin(self):
        return self.last_rotated == None or  (time.time() - self.last_rotated) < VaultTTLSyncConstant.VAULT_TOKEN_TTL

    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):        
        if not self.is_loggedin:
            raise ServiceTemporaryNotAvailableError(service=self.name)

    def build(self, build_state = DEFAULT_BUILD_STATE):
        # if self.configService.VAULT_ACTIVATED:
        #     raise BuildOkError
        if self.configService.MODE == MODE.DEV_MODE:
            self._dev_token_login()
            self.read_tokens()
        else:
            seed_time = self._read_volume_file(VaultConstant.SUPERCRONIC_SEED_TIME_FILE,'shared')
            if seed_time and isinstance(seed_time,str):
                self.supercronic_start_time = float(seed_time.split('=')[1])
                self.compute_next_tick_time()

            self.vault_approle_login(build_state)
            print(self.client.token)
            self.read_tokens()
            self.interval_schedule(self.delay,self.refresh_token,tuple(),{},f'{self.name}-refresh_token')

    def compute_next_tick_time(self):
        tick_delay = time_until_next_tick(self._secret_id_crontab)
        self.next_tick = time.time() + tick_delay
            
    def _create_client(self,build_state:int):
        self.client = hvac.Client(self.configService.VAULT_ADDR)
        self.client.session.headers.update({
            "X-Vault-Node-Name": self.uvicornWorkerService.INSTANCE_ID,
        })
        _raise = build_state==DEFAULT_BUILD_STATE or build_state == GUNICORN_BUILD_STATE

        if build_state == DEFAULT_BUILD_STATE or build_state == GUNICORN_BUILD_STATE:
            self.role_id = self._read_volume_file(VaultConstant.ROLE_ID_FILE,'secrets',_raise)
            self.secret_id = self._read_volume_file(VaultConstant.SECRET_ID_FILE,'shared',_raise)

        self.client.auth.approle.login(self.role_id,self.secret_id)

        if not self.client.is_authenticated():
            return False
        
        self.token_meta = parse_vault_token_meta(self.client.lookup_token())
        
        self.secrets_engine = KV1VaultEngine(self.client, VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT)
        self.generation_engine = KV2VaultEngine(self.client,VaultConstant.NOTIFYR_GENERATION_MOUNT_POINT)
        self.transit_engine = TransitVaultEngine(self.client,VaultConstant.NOTIFYR_TRANSIT_MOUNT_POINT)
        self.database_engine = DatabaseVaultEngine(self.client,VaultConstant.NOTIFYR_DB_MOUNT_POINT)
        self.minio_engine = MinioS3VaultEngine(self.client,VaultConstant.NOTIFYR_MINIO_MOUNT_POINT)
        self.rabbitmq_engine = RabbitMQVaultEngine(self.client,VaultConstant.NOTIFYR_RABBITMQ_MOUNT_POINT)

        return True

    async def refresh_token(self):

        async with self.statusLock.writer as locK:            
            creation_state = DEFAULT_BUILD_STATE if  time.time() > self.next_tick else 0
            self.compute_next_tick_time()
            try:
                if not self._create_client(creation_state):
                    self.service_status = ServiceStatus.TEMPORARY_NOT_AVAILABLE
                else:
                    self.service_status = ServiceStatus.AVAILABLE
                    self.last_rotated = time.time()

            except BuildAbortError:
                self.service_status = ServiceStatus.NOT_AVAILABLE
            except requests.exceptions.ConnectionError as e:
                self.service_status = ServiceStatus.MAJOR_SYSTEM_FAILURE
            except requests.exceptions.Timeout as e:
                self.service_status = ServiceStatus.MAJOR_SYSTEM_FAILURE
            except Exception as e:
                print(e,e.__class__) 
                try:
                    self.renew_auth_token()
                    self.last_rotated = time.time()
                    self.service_status = ServiceStatus.PARTIALLY_AVAILABLE
                except:
                    self.service_status = ServiceStatus.NOT_AVAILABLE
            
            print(f'{self.name}:',self.service_status)
    
    def _read_volume_file(self,filename:str,t:Literal['shared','secrets'],raise_:bool=True):

        callback = VaultConstant.VAULT_SHARED_DIR if t == 'shared' else VaultConstant.VAULT_SECRET_DIR
        filename_ = callback(filename)
        content:str = self.fileService.readFile(filename_,FDFlag.READ)
        _,last_modified = self.fileService.get_file_info(filename_)
        
        if content != None:
            return content.strip()
        else:
            if raise_:
                raise BuildAbortError(f'Could not get the {filename}')

        return content

    def destroy(self, destroy_state = DEFAULT_DESTROY_STATE):
        self.client.logout()

##############################################                          ##################################333

    def vault_approle_login(self,build_state):
        try:
            if not self._create_client(build_state):
                raise BuildAbortError('Not authenticated')
            
            if not self.client.ha_status['is_self']:
                self.service_status = ServiceStatus.PARTIALLY_AVAILABLE

            if not self.client.seal_status['initialized']:
                raise BuildAbortError('Vault Db is not initialized')
            
            if self.client.seal_status['sealed']:
                raise BuildAbortError('Cant access vault since it sealed')
            
        except hvac.exceptions.InvalidRequest as e:
            raise BuildAbortError(f'"Invalid:", {e}')
        except hvac.exceptions.InternalServerError as e:
            raise BuildAbortError(f"IntervalServerError {e}")
        except hvac.exceptions.Forbidden as e:
            raise BuildAbortError(f"Forbidden: {e}")
        except hvac.exceptions.Unauthorized as e:
            raise BuildAbortError(f"Unauthorized: {e}")
        except hvac.exceptions.VaultDown:
            raise BuildAbortError('Vault Is Sealed')
        except requests.exceptions.ConnectionError as e:
            raise BuildAbortError(f"Vault server not reachable: {e}")
        except requests.exceptions.Timeout as e:
            raise BuildAbortError("Vault request timed out: {e}")
  
    def _dev_token_login(self):
        dev_root_token = self.configService.getenv('VAULT_DEV_ROOT_TOKEN_ID',None)
        if not dev_root_token:
            raise BuildAbortError('No dev root token provided')
        try:
            self.client = hvac.Client(self.configService.VAULT_ADDR,token=dev_root_token)
        except Exception as e:
            raise BuildAbortError(f"Failed to create Vault client: {e}")
        
##############################################                          ##################################333

    def renew_auth_token(self):
        return self.client.auth.token.renew_self()

    def revoke_auth_token(self):
        try:
            return self.client.auth.token.revoke_self()
        except:
            ...

    def renew_lease(self,lease_id,increment):
        ...

    def revoke_lease(self,lease_id:str):
        try:
            return self.client.sys.revoke_leases(lease_id=lease_id)
        except:
            ...

##############################################                          ##################################333

    def read_tokens(self):
        self.tokens = self.secrets_engine.read(VaultConstant.TOKENS_SECRETS)
    
    @property
    def JWT_SECRET_KEY(self):
        return self.tokens.get('JWT_SECRET_KEY',None)
   
    @property
    def JWT_ALGORITHM(self):
        return self._jwt_algorithm

    @property
    def ON_TOP_SECRET_KEY(self):
        token = self.tokens.get('ON_TOP_SECRET_KEY',None)
        return token[:32] if token else None
    
    @property
    def API_ENCRYPT_TOKEN(self):
        return self.tokens.get('API_ENCRYPT_TOKEN',None)
    
    @property
    def CONTACTS_HASH_KEY(self):
        return self.tokens.get('CONTACTS_HASH_KEY',None)
    
    @property
    def CONTACT_JWT_SECRET_KEY(self):
        return self.tokens.get('CONTACT_JWT_SECRET_KEY',None)

    @property
    def WS_JWT_SECRET_KEY(self):
        return self.tokens.get('WS_JWT_SECRET_KEY',None)
    
    @property
    def CLIENT_PASSWORD_HASH_KEY(self):
        return self.tokens.get('CLIENT_PASSWORD_HASH_KEY',None)
    
    @property
    def RSA_SECRET_PASSWORD(self):
        return self.tokens.get('RSA_SECRET_PASSWORD',None)


    
