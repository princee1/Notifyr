from app.definition._service import BaseService, Service
from app.services.config_service import ConfigService
from app.services.database.rabbitmq_service import RabbitMQService
from app.services.database.redis_service import RedisService

@Service()
class TaskiqService(BaseService):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,rabbitmqService:RabbitMQService):
        super().__init__()
    
    def build(self, build_state = ...):
        return super().build(build_state)