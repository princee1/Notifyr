from typing import Any
from typing_extensions import Literal
from .config_service import ConfigService
from .file_service import FileService
from app.definition._service import Service,AbstractServiceClass,ServiceClass
import sqlite3
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient,AsyncIOMotorClientSession,AsyncIOMotorDatabase
from odmantic import AIOEngine

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
    DB = Literal['agent','chat']

    #NOTE SEE https://motor.readthedocs.io/en/latest/examples/bulk.html
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)
        self.db_ref:dict[MongooseService.DB,Any] =  {}
        self.mongo_uri = self.configService.getenv('MONGO_URI')
    
    def build(self):
        try:    
            agentDB_name =self.configService.getenv('MONGO_AGENT_DB')
            chatDB_name = self.configService.getenv('MONGO_CHAT_DB')

            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.agent_engine = AIOEngine(self.client,agentDB_name)
            self.chat_engine = AIOEngine(self.client,chatDB_name)
            
            self.db_ref['agent'] = {
                'engine':self.agent_engine,
                'db':AsyncIOMotorDatabase(self.client,agentDB_name)
            }
            self.db_ref['chat'] = {
                'engine':self.chat_engine,
                'db':AsyncIOMotorDatabase(self.client,chatDB_name)
            }
        except: # TODO 
            raise ...    
@ServiceClass
class RedisService(DatabaseService):
    
    def __init__(self,configService:ConfigService):
        super().__init__(configService,None)
        self.configService = configService

    def build(self):
        ...

    def refund(self, limit_request_id:str):
        ...

    def store(self,):
        ...
    
    def store_bkg_result(data,key):
        ...

@ServiceClass
class TortoiseConnectionService(DatabaseService):

    def __init__(self, configService:ConfigService):
        super().__init__(configService,None)

    def build(self):
        ...
    
    