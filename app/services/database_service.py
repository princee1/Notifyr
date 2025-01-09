from .config_service import ConfigService
from .file_service import FileService
from .security_service import SecurityService
from definition._service import Service,AbstractServiceClass,ServiceClass
import sqlite3
import pandas as pd

@AbstractServiceClass
class DatabaseService(Service): 
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
            super().__init__()
            self.configService= configService
            self.fileService = fileService


@ServiceClass
class SQLiteService(DatabaseService):
    def __init__(self,configService:ConfigService, securityService:SecurityService, fileService:FileService) -> None:
        super().__init__(configService,fileService)
        self.securityService = securityService
    

@ServiceClass
class CSVService(DatabaseService):

    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)
    ...

@ServiceClass
class MongooseService(DatabaseService):
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)
    

@ServiceClass
class SQLService(DatabaseService):
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)

