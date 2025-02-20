"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

from typing import Annotated
from fastapi import Header
from app.definition import _service
from app.services.logger_service import LoggerService
from .config_service import ConfigService
from app.utils.helper import b64_encode
#from twilio.rest import Client



@_service.ServiceClass
class TwilioService(_service.Service):
    def __init__(self, configService: ConfigService,) -> None:
        super().__init__()
        self.configService = configService

    def build(self):
        # self.client = Client(self.configService.TWILIO_ACCOUNT_SID,
        #                      self.configService.TWILIO_AUTH_TOKEN)
        return super().build()
    
    
@_service.AbstractServiceClass
class BaseTwilioCommunication(_service.Service):
    def __init__(self, configService: ConfigService, twilioService: TwilioService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService
    
    async def verify_twilio_token(self,x_twilio_signature: Annotated[str, Header()]):
        ...


@_service.ServiceClass
class SMSService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)

    def build(self):
        #self.message = self.twilioService.client.messages
        return super().build()
        
    pass


@_service.ServiceClass
class VoiceService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)
    pass


@_service.ServiceClass
class FaxService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)


@_service.ServiceClass
class SIPService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)


@_service.ServiceClass
class WhatsAppService(BaseTwilioCommunication):
    def __init__(self, configService: ConfigService, loggerService: LoggerService,twilioService: TwilioService):
        super().__init__(configService,twilioService)
        self.loggerService = loggerService
