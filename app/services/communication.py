from injector import inject
from . import _service

from .config import ConfigService
from .twillo import TwilioService


class SMSService(_service.Service):
    def __init__(self,configService: ConfigService, twilioService: TwilioService): pass
    pass

class PhoneService(_service.Service):
    def __init__(self,configService: ConfigService, twilioService: TwilioService): pass
    pass