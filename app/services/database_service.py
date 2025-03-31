from .config_service import ConfigService
from .file_service import FileService
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
class SQLiteService(DatabaseService):
    def __init__(self,configService:ConfigService, fileService:FileService) -> None:
        super().__init__(configService,fileService)


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
class RedisService(Service):
    
    def __init__(self,configService:ConfigService):
        super().__init__()
        self.configService = configService

    def build(self):
        ...

    def refund(self, limit_request_id:str):
        ...

    def store(self,):
        ...
    
    def store_bkg_result(data,key):
        ...

    
