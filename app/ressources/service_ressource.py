from app.definition._ressource import BaseHTTPRessource, UsePermission
from app.services.config_service import ConfigService



class ServiceRessource(BaseHTTPRessource):
    
    def __init__(self, configService:ConfigService):
        super().__init__()
        self.configService = configService
    

    async def refresh(self):
        ...

