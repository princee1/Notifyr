
from injector import inject
from .config import ConfigService
from ._module import Module


class SecurityService(Module):
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
