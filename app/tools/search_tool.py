from app.definition._tool import  DiscoveryTool
from app.models.odm.outbound_model import HTTPOutboundModel
from app.models.tools_model import SearchToolModel
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.qdrant_service import QdrantService
from app.services.profile_service import ProfileMiniService

#Source: database lookup, Youtube search, internet search (duck duck go), wikipedia,ionic assitant shopping tools, redditSearch

class SearchTool(DiscoveryTool):

    def __init__(self,configService:ConfigService,qdrantService:QdrantService,customService:CustomService,config:SearchToolModel,httpOutboundService:ProfileMiniService[HTTPOutboundModel]=None):
        super().__init__(config)
        self.configService = configService
        self.httpOutboundService = httpOutboundService
        self.qdrantService = qdrantService
        self.customService = customService
        self.config = config
    
    async def __call__(self,query:str):
        ...
