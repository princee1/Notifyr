from injector import inject
from app.services.config import ConfigService
from module import Module

class LoggerService(Module):

    @inject
    def __init__(self,configService: ConfigService) -> None:
        self.configService = configService  
    pass