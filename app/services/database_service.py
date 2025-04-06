import functools
from typing import Any, Callable
from typing_extensions import Literal

from app.definition._error import BaseError
from .config_service import ConfigService
from .file_service import FileService
from app.definition._service import Service,AbstractServiceClass,ServiceClass
import sqlite3
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient,AsyncIOMotorClientSession,AsyncIOMotorDatabase
from odmantic import AIOEngine
from redis.asyncio import Redis



class RedisDatabaseDoesNotExistsError(BaseError):
    ...

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
        
    @staticmethod
    def check_db(func:Callable):

        @functools.wraps(func)
        async def wrapper(self:RedisService,database:int|str,*args,**kwargs):
            if not kwargs['redis'] or  not isinstance(kwargs['redis'],Redis):
                ... # TODO if should keep the instance passed

            if database not in self.db[database]:
                raise RedisDatabaseDoesNotExistsError(database)
            kwargs['redis'] = self.db[database]
            return await func(self,database,*args,**kwargs)

        return wrapper

    def build(self):
        self.redis_celery = Redis(host=self.configService.REDIS_URL,db=0)
        self.redis_limiter = Redis(host=self.configService.REDIS_URL,db=1)
        #self.redis_cache = Redis(host=self.configService.REDIS_URL,db=2)
        self.db:dict[int,Redis] = {
            0:self.redis_celery,
            1:self.redis_limiter,
            #2:self.redis_cache,
            'celery':self.redis_celery,
            'limiter':self.redis_limiter,
        }

    async def refund(self, limit_request_id:str):
        redis = self.db[1]
        if not await self.retrieve(1,limit_request_id):
            return
        return await redis.decr(limit_request_id)

    @check_db
    async def store(self,database:int|str,key:str,value:Any,expiry,redis:Redis=None):
        return await redis.set(key,value,ex=expiry)
    
    @check_db
    async def retrieve(self,database:int|str,key:str,redis:Redis=None):
        return await redis.get(key)
    
    @check_db
    async def append(self,database:int|str,key:str,data:Any,redis:Redis=None):
        return await redis.append(key,data)
    
    async def store_bkg_result(self,data,key):
        if not await self.retrieve(0,key):
            response = await self.store(0,key,[data])
        else:
            response = await self.append(0,key,data)
        return response
            
            

@ServiceClass
class TortoiseConnectionService(DatabaseService):

    def __init__(self, configService:ConfigService):
        super().__init__(configService,None)

    def build(self):
        ...
    
    