from .config_service import ConfigService
from .file_service import FileService
from .security_service import SecurityService
from definition._service import Service,AbstractServiceClass,ServiceClass
from injector import inject
import sqlite3

@AbstractServiceClass
class DatabaseService(Service): pass

@ServiceClass
class SQLiteService(DatabaseService):
    @inject
    def __init__(self,configService:ConfigService, securityService:SecurityService, fileService:FileService) -> None:
        super().__init__()
        self.configService= configService
        self.securityService = securityService
        self.fileService = fileService
    pass