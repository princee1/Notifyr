from app.definition._service import MiniBaseService, Service
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService

@Service()
class WorkflowService(MiniBaseService):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService,):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService