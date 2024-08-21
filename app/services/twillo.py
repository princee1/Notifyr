from . import _service
from .config import ConfigService
from injector import inject

class TwilioService(_service.Service):
    @inject
    def __init__(self,configService: ConfigService):
        super.__init__()
        self.configService = configService
