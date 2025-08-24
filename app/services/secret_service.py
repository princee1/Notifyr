
from app.definition._service import BaseService, Service
from app.services.aws_service import AmazonSecretManagerService
from app.services.config_service import ConfigService


@Service
class HashiVaultService(BaseService):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService = configService


@Service
class VaultSecretService(BaseService):
    
    def __init__(self,configService:ConfigService, awsSecretService:AmazonSecretManagerService,hashiVaultService:HashiVaultService):
        super().__init__()
        
        self.configService=configService
        self.awsSecretService = awsSecretService
        self.hashiVaultService = hashiVaultService
        

