from .config import ConfigService
from .file import FileService
from .security import SecurityService
from interface._service import Service,AbstractServiceClass
from injector import inject
import sqlite3

@AbstractServiceClass
class DatabaseService(Service): pass

class SQLiteService(DatabaseService):
    @inject
    def __init__(self,configService:ConfigService, securityService:SecurityService, fileService:FileService) -> None:
        super().__init__()
        self.configService= configService
        self.securityService = securityService
        self.fileService = fileService
    pass