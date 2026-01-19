from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService

@HTTPRessource()
class ChatRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,mongooseService:MongooseService,configService:ConfigService):
        super().__init__(None,None)
        self.mongooseService = mongooseService
        self.configService = configService

    
    async def fetch_message(self):
        ...
    
    async def delete_message(self):
        ...

    async def fetch_analytics(self):
        ...

    