from injector import inject
from . import _service
from .config import ConfigService


class TwilioService(_service.Service):
    @inject
    def __init__(self,configService: ConfigService):
        super.__init__()
        self.configService = configService

_service.AbstractServiceClass()
class BaseTwilioCommunication(_service.Service):
    def __init__(self,configService: ConfigService, twilioService: TwilioService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService

class SMSService(BaseTwilioCommunication):
    def __init__(self,configService: ConfigService, twilioService: TwilioService):
        super.__init__(configService,twilioService)
    pass

class PhoneService(BaseTwilioCommunication):
    def __init__(self,configService: ConfigService, twilioService: TwilioService):
        super.__init__(configService,twilioService)

    pass