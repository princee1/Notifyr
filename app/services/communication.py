from injector import inject
from . import _module

from .config import ConfigService
from .twillo import TwilioService


class SMSService(_module.Module):
    def __init__(self,configService: ConfigService, twilioService: TwilioService): pass
    pass

class PhoneService(_module.Module):
    def __init__(self,configService: ConfigService, twilioService: TwilioService): pass
    pass