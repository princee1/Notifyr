from app.definition._tool import Pipeline
from app.services.config_service import ConfigService
from app.services.database.graphiti_service import GraphitiService

class KnowledgeGraphRagPipeline(Pipeline):
    
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService):
        super().__init__()
        self.graphitiService = graphitiService
        self.configService = configService


    async def __call__(self):
        ...