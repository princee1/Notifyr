from app.definition._tool import  Tool,Pipeline
from app.services.config_service import ConfigService
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService
from app.services.mini.outbound.http_outbound_service import HTTPOutboundMiniService

class SearchPipeline(Pipeline):

    def __init__(self,configService:ConfigService,httpOutboundService:HTTPOutboundMiniService,memcachedService:MemCachedService,qdrantService:QdrantService):
        self.configService = configService
        self.httpOutboundService = httpOutboundService
        self.memcachedService = memcachedService
        self.qdrantService = qdrantService
    
    async def __call__(self,):
        ...
