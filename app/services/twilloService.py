from module import Module
from services.configService import ConfigService
from injector import inject

class TwilioService(Module):
    @inject
    def __init__(self,configService: ConfigService): pass