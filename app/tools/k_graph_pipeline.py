from app.definition._tool import Pipeline
from app.services.config_service import ConfigService
from app.services.database.bolt_service import BoltService

class KnowledgeGraphRagPipeline(Pipeline):
    
    def __init__(self,boltService:BoltService,configService:ConfigService):
        super().__init__()
        self.boltService = boltService
        self.configService = configService


    async def __call__(self):
        ...