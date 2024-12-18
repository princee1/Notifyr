from injector import inject
from definition import _service
from .config_service import ConfigService
from logging import Logger, LogRecord
import sqlite3


@_service.ServiceClass
class LoggerService(_service.Service):

    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService
    pass
