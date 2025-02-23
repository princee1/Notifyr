"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

from typing import Annotated
from fastapi import HTTPException, Header, Request
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
    
    async def verify_twilio_token(self,request:Request):
        twilio_signature = request.headers.get("X-Twilio-Signature", "")

        full_url = str(request.url)

        form_data = await request.form()
        params = {key: form_data[key] for key in form_data}

        validator = RequestValidator(self.configService.TWILIO_AUTH_TOKEN)
        if not validator.validate(full_url, params, twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio Signature")
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
