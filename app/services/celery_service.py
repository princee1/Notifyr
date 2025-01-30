from app.definition._service import Service, ServiceClass
from .config_service import ConfigService
from app.interface.threads import InfiniteAsyncInterface


@ServiceClass
class CeleryService(Service,InfiniteAsyncInterface):
    def __init__(self,configService:ConfigService,):
        Service.__init__(self)
        InfiniteAsyncInterface.__init__(self)
        self.configService = configService
    
    
    

