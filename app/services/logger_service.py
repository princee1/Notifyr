from injector import inject
from app.definition import _service
from .config_service import ConfigService
from logging import Logger, LogRecord
import sqlite3


@_service.Service()
class LoggerService(_service.BaseService):

    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService
    
    def build(self,build_state=-1):
       ...
