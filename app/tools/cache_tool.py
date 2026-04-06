from app.definition._tool import Tool
from app.services import ConfigService
from app.services import QdrantService
from app.services import MemCachedService

class CacheTool(Tool):
    
    def __init__(self,configService:ConfigService,qdrantService:QdrantService,memcachedService:MemCachedService):
        self.configService = configService
        self.qdrantService = qdrantService
        self.memcachedService = memcachedService

    async def __call__(self, *args, **kwds):
        return super().__call__(*args, **kwds)