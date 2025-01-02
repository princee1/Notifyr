from definition._service import Service,ServiceClass
from .config_service import ConfigService
from .logger_service import LoggerService

class WhatsAppService(Service):
    def __init__(self, configService: ConfigService, loggerService: LoggerService):
        super().__init__()
        self.configService = configService
        self.loggerService = loggerService
