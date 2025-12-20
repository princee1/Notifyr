from app.definition._service import Service,BaseService
from app.errors.service_error import BuildWarningError
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.logger_service import LoggerService
from app.utils.globals import CAPABILITIES

@Service()
class WorkflowService(BaseService):

    def __init__(self,configService:ConfigService,mongooseService:MongooseService,loggerService:LoggerService):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.loggerService = loggerService

    def build(self, build_state = ...):
        return super().build(build_state)

    def verify_dependency(self):
        if CAPABILITIES['workflow']:
            raise BuildWarningError
