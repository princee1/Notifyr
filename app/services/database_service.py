from .config_service import ConfigService
from .file_service import FileService
from .security_service import SecurityService
from app.definition._service import Service,AbstractServiceClass,ServiceClass
import sqlite3
import pandas as pd

@AbstractServiceClass
class DatabaseService(Service): 
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
            super().__init__()
            self.configService= configService
            self.fileService = fileService


@ServiceClass
class SQLiteService(DatabaseService): # logging
    def __init__(self,configService:ConfigService, securityService:SecurityService, fileService:FileService) -> None:
        super().__init__(configService,fileService)
        self.securityService = securityService
    

@ServiceClass
class CSVService(DatabaseService): # analytics

    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)
    ...

@ServiceClass
class MongooseService(DatabaseService): # Chat data
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)
    

@ServiceClass
class SQLService(DatabaseService): # token blacklist data
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)

