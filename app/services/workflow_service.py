from app.definition._service import Service,BaseService
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService, RedisService
from app.services.logger_service import LoggerService
from app.services.reactive_service import ReactiveService
from app.services.task_service import CeleryService

@Service()
class WorkflowService(BaseService):

    def __init__(self,configService:ConfigService,mongooseService:MongooseService,loggerService:LoggerService,reactiveService:ReactiveService,celeryService:CeleryService,redisService:RedisService):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.loggerService = loggerService
        self.reactiveService = reactiveService
        self.celeryService = celeryService
        self.redisService = redisService

    