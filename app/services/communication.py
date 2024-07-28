from injector import inject
from . import _module

from .config import ConfigService


class SMSService(_module.Module):
    def __init__(self,configService: ConfigService): pass
    pass

class PhoneService(_module.Module):
    def __init__(self,configService: ConfigService): pass
    pass