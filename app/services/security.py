
from injector import inject
from module import Module
from app.services.config import ConfigService

class SecurityService(Module):
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
