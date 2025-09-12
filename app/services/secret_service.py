import datetime
from typing import Literal, TypedDict
import requests
from app.classes.vault_engine import DatabaseVaultEngine, KV1VaultEngine, KV2VaultEngine, TransitVaultEngine
from app.definition._service import DEFAULT_BUILD_STATE, DEFAULT_DESTROY_STATE, BaseService, BuildAbortError, Service, ServiceStatus
from app.interface.timers import IntervalInterface
from app.services.config_service import MODE, ConfigService
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


@Service
class HCVaultService(BaseService,IntervalInterface):

    _secret_id_crontab='0 * * * *'
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
        IntervalInterface.__init__(self,False,VaultTTLSyncConstant.SECRET_ID_TTL)
        self._jwt_algorithm = self.configService.getenv("JWT_ALGORITHM",DEFAULT_JWT_ALGORITHM)

    def verify_dependency(self):
        ...

    def build(self, build_state = DEFAULT_BUILD_STATE):
        
        if self.configService.MODE == MODE.DEV_MODE:
            self._dev_token_login()
            self.read_tokens()
        else:
            seed_time = self._read_volume_file(VaultConstant.SUPERCRONIC_SEED_TIME_FILE,'shared')
            if seed_time and isinstance(seed_time,str):
                self.supercronic_start_time = float(seed_time.split('=')[1])
                self._secret_id_crontab_interval = cron_interval(self._secret_id_crontab,self.supercronic_start_time)

            self.vault_approle_login(build_state)
            print(self.client.lookup_token())
            print(self.client.token)
            self.read_tokens()
            
    def _create_client(self,build_state:int):
        self.client = hvac.Client(self.configService.VAULT_ADDR)
        _raise = build_state==DEFAULT_BUILD_STATE

        if build_state == DEFAULT_BUILD_STATE:
            self.role_id = self._read_volume_file(VaultConstant.ROLE_ID_FILE,'secrets',_raise)
            self.secret_id = self._read_volume_file(VaultConstant.SECRET_ID_FILE,'shared',_raise)

        self.client.auth.approle.login(self.role_id,self.secret_id)

        if not self.client.is_authenticated():
            return False
        
        self.token_meta = parse_vault_token_meta(self.client.lookup_token())
        
        self._kv1_engine = KV1VaultEngine(self.client)
        self._kv2_engine = KV2VaultEngine(self.client)
        self._transit_engine = TransitVaultEngine(self.client)
        self._database_engine = DatabaseVaultEngine(self.client)

        return True

    async def callback(self):

        async with self.statusLock.writer as locK:
            tick_ratio = time_until_next_tick(self._secret_id_crontab)/self._secret_id_crontab_interval
            creation_state = DEFAULT_BUILD_STATE if  tick_ratio < 0.1 else 1

            try:
                print(self.renew_auth_token())
                return

                if not self._create_client(creation_state):
                    self.service_status = ServiceStatus.MAJOR_SYSTEM_FAILURE
                else:
                    self.service_status = ServiceStatus.AVAILABLE
            except:
                ...


                


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
        except requests.exceptions.ConnectionError as e:
            raise BuildAbortError(f"Vault server not reachable: {e}")
        except requests.exceptions.Timeout as e:
            raise BuildAbortError("Vault request timed out: {e}")
  
    def _dev_token_login(self):
        try:
            ...
        except:
            ...

    def renew_auth_token(self):
        return self.client.auth.token.renew_self()

##############################################                          ##################################333

    def renew_lease(self,lease_id,increment):
        ...

##############################################                          ##################################333

    def generate_mongo_creds(self):
        return self._database_engine.generate_credentials(VaultConstant.MONGO_ROLE)
    
    def generate_postgres_creds(self):
        return self._database_engine.generate_credentials(VaultConstant.POSTGRES_ROLE)

##############################################                          ##################################333

    def read_profile(self,profiles_id:str):
        data = self._kv1_engine.read(VaultConstant.PROFILES_SECRETS,profiles_id)
        for k,v in data.items():
            data[k]= self._transit_engine.decrypt(v,VaultConstant.PROFILES_KEY)
        return data

    def put_profiles(self,profiles_id:str,data:dict):
        for k,v in data.items():
            data[k] = self._transit_engine.encrypt(v,VaultConstant.PROFILES_KEY)
        data = {
            profiles_id:data
        }
        return self._kv1_engine.put(VaultConstant.PROFILES_SECRETS,profiles_id,data)

    def delete_profiles(self,profiles_id:str):
        return self._kv1_engine.delete(VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,profiles_id)

    def read_tokens(self):
        self.tokens = self._kv1_engine.read(VaultConstant.TOKENS_SECRETS)
    
##############################################                          ##################################333

    def read_generation_id(self):
        ...

##############################################                          ##################################333


    @property
    def JWT_SECRET_KEY(self):
        return self.tokens.get('JWT_SECRET_KEY',None)

    
    @property
    def JWT_ALGORITHM(self):
        return self._jwt_algorithm

    @property
    def ON_TOP_SECRET_KEY(self):
        return self.tokens.get('ON_TOP_SECRET_KEY',None)
    
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
    def RSA_PASSWORD(self):
        return self.tokens.get('RSA_PASSWORD',None)


    
