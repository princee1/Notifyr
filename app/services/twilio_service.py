"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

from injector import inject
from definition import _service
from .config_service import ConfigService
from twilio.rest import Client


@_service.ServiceClass
class TwilioService(_service.Service):
    @inject
    def __init__(self, configService: ConfigService):
        super().__init__()
        self.configService = configService

    def build(self):
        # self.client = Client(self.configService.TWILIO_ACCOUNT_SID,
        #                      self.configService.TWILIO_AUTH_TOKEN)
        ...


@_service.AbstractServiceClass
class BaseTwilioCommunication(_service.Service):
    def __init__(self, configService: ConfigService, twilioService: TwilioService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService


@_service.ServiceClass
class SMSService(BaseTwilioCommunication):

    @inject
    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)

    def build(self):
        #self.message = self.twilioService.client.messages
        ...

    def send_message(self, to, body):
        self.message.create(to, body=body)
        pass
    pass


@_service.ServiceClass
class VoiceService(BaseTwilioCommunication):

    @inject
    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)
    pass


@_service.ServiceClass
class FaxService(BaseTwilioCommunication):

    @inject
    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)


@_service.ServiceClass
class SIPService(BaseTwilioCommunication):

    @inject
    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)
