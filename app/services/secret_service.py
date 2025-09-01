
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.interface.timers import IntervalInterface
from app.services.aws_service import AmazonSecretManagerService
from app.services.config_service import MODE, ConfigService
from pathlib import Path

# @Service
# class SecretService(BaseService):
    
#     def __init__(self,configService:ConfigService, awsSecretService:AmazonSecretManagerService,hashiVaultService:HashiVaultService):
#         super().__init__()
        
#         self.configService=configService
#         self.awsSecretService = awsSecretService
#         self.hashiVaultService = hashiVaultService
        

def VAULT_SECRET_DIR()->str:
    return ''


SECRET_ID_FILE= 'secret_id' 
ROLE_ID_FILE = 'role_id.txt' # in the secrets shared by the vault


@Service
class HashiCorpVaultService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService = configService
        IntervalInterface.__init__(self,False,1000)

    def verify_dependency(self):
        ...

    def build(self, build_state = DEFAULT_BUILD_STATE):
        if self.configService.MODE == MODE.DEV_MODE:
            ...
        
        else: 
            try:
                self.role_id = Path().read_text()
            except:
                ...
            
            self.read_secret_id()

    async def callback(self):
        async with self.statusLock.writer as locK:
            self.read_secret_id()

    def read_secret_id(self):
        try:
            self.secret_id = Path().read_text()
        except:
            ...

        



    
