from app.definition._tool import Pipeline
from app.services.config_service import ConfigService
from app.services.database.neo4j_service import Neo4JService

class KnowledgeGraphRagPipeline(Pipeline):
    
    def __init__(self,neo4JService:Neo4JService,configService:ConfigService):
        super().__init__()
        self.neo4JService = neo4JService
        self.configService = configService
