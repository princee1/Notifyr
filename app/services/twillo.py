from . import _module
from .config import ConfigService
from injector import inject

class TwilioService(_module.Module):
    @inject
    def __init__(self,configService: ConfigService): pass