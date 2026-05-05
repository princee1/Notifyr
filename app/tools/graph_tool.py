from app.definition._tool import ContextPipelineTool
from app.models.tools_model import KnowledgeGraphToolModel
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.graphiti_service import GraphitiService
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService

class KnowledgeGraphTool(ContextPipelineTool):
    
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService,customService:CustomService,qdrantService:QdrantService,config:KnowledgeGraphToolModel):
        super().__init__(config)
        self.graphitiService = graphitiService
        self.configService = configService
        self.customService = customService
        self.qdrantService = qdrantService
        self.config = config

    async def __call__(self):
        ...
    
    async def search(self):
        ...


class MemoryTool(KnowledgeGraphTool):
    
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService,customService:CustomService,qdrantService:QdrantService):
        config = self._to_base_config()
        super().__init__(graphitiService,configService,customService,qdrantService,config)

    def _to_base_config(self)->KnowledgeGraphToolModel:
        ...

    async def __call__(self,query:str ):
        ...