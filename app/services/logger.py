from injector import inject
from interface import _service
from .config import ConfigService
from logging import Logger, LogRecord
import sqlite3

class LoggerService(_service.Service):

    @inject
    def __init__(self,configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService  
    pass