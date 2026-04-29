from app.definition._tool import  DiscoveryTool
from app.models.agents_model import SearchToolModel
from app.services.config_service import ConfigService
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService
from app.services.mini.outbound.http_outbound_service import HTTPOutboundMiniService

class SearchTool(DiscoveryTool):

    def __init__(self,configService:ConfigService,httpOutboundService:HTTPOutboundMiniService,memcachedService:MemCachedService,qdrantService:QdrantService,config:SearchToolModel):
        super().__init__(config)
        self.configService = configService
        self.httpOutboundService = httpOutboundService
        self.memcachedService = memcachedService
        self.qdrantService = qdrantService
        self.config = config
    
    async def __call__(self,query:str):
        ...
