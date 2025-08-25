from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from .database_service import MongooseService

@Service
class ProfileService(BaseService):

    def __init__(self, mongooseService: MongooseService, configService: ConfigService):
        self.mongooseService = mongooseService
        self.configService = configService