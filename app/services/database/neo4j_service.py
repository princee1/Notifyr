from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.vault_service import VaultService

@Service()
class Neo4JService(BaseService):
    
    def __init__(self,configService:ConfigService,vaultService:VaultService):
        super().__init__()
        self.vaultService = vaultService