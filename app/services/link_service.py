from app.definition._service import Service, ServiceClass
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.reactive_service import ReactiveService


@ServiceClass
class LinkService(Service):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,reactiveService:ReactiveService):
        super().__init__()
        self.configService = configService
        self.base_url = self.configService
        self.reactiveService = reactiveService
        self.redisService = redisService
    
    def build(self):
        ...
    

    def verify_safe_domain(self,):
        ...
    
    def verify_server_well_know(self,):
        ...