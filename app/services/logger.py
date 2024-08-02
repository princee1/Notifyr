from injector import inject
from . import _service
from config import ConfigService

class LoggerService(_service.Service):

    @inject
    def __init__(self,configService: ConfigService) -> None:
        self.configService = configService  
    pass