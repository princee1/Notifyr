from injector import inject
from . import _module
from config import ConfigService

class LoggerService(_module.Module):

    @inject
    def __init__(self,configService: ConfigService) -> None:
        self.configService = configService  
    pass