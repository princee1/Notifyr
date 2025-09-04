from typing import Literal
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, BuildAbortError, Service
from app.interface.timers import IntervalInterface
from app.services.aws_service import AmazonSecretManagerService
from app.services.config_service import MODE, ConfigService
from pathlib import Path
from app.services.database_service import RedisService
# @Service
# class SecretService(BaseService):
    
#     def __init__(self,configService:ConfigService, awsSecretService:AmazonSecretManagerService,hashiVaultService:HashiVaultService):
#         super().__init__()
        
#         self.configService=configService
#         self.awsSecretService = awsSecretService
#         self.hashiVaultService = hashiVaultService
        

def VAULT_SECRET_DIR(file:str)->str:
    return f'/vault/secrets/{file}'

def VAULT_SHARED_DIR(file:str)->str:
    return f'/vault/shared/{file}'


SECRET_ID_FILE= 'secret_id.txt' 
ROLE_ID_FILE = 'role_id.txt' # in the secrets shared by the vault
SUPERCRONIC_SEED_TIME_FILE = 'seed-time.txt'




@Service
class HashiCorpVaultService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService,redisService:RedisService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        IntervalInterface.__init__(self,False,1000)

    def verify_dependency(self):
        ...

    def build(self, build_state = DEFAULT_BUILD_STATE):
        
        if self.configService.MODE == MODE.DEV_MODE:
            ...
        
        else: 
            self.role_id = self.read_volume_file(ROLE_ID_FILE,'secrets')
            self.supercronic_start_time = self.read_volume_file(SUPERCRONIC_SEED_TIME_FILE,'shared')
            
    async def callback(self):
        async with self.statusLock.writer as locK:
            self.secret_id = self.read_volume_file(SECRET_ID_FILE,'shared',False)

    def read_volume_file(self,filename:str,t:Literal['shared','secrets'],raise_:bool=True):

        callback = VAULT_SHARED_DIR if t == 'shared' else VAULT_SECRET_DIR
        file = callback(filename)
        path = Path(file)
        if not path:
            if raise_:
                raise BuildAbortError
        try:
            return path.read_text()
        except:
            ...

        



    
