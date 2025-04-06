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
import json



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
        async def wrapper(self,database:int|str,*args,**kwargs):
            if 'redis' in kwargs and (not kwargs['redis'] or  not isinstance(kwargs['redis'],Redis)):
                ... # TODO if should keep the instance passed

            if database not in self.db:
                raise RedisDatabaseDoesNotExistsError(database)
            kwargs['redis'] = self.db[database]
            #return await None# ERROR
            return await func(self,database,*args,**kwargs)

        return wrapper

    def build(self):
        host = self.configService.REDIS_URL.split('//')[1]
        self.redis_celery = Redis(host=host,db=0)
        self.redis_limiter = Redis(host=host,db=1)
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
        if isinstance(value,(dict,list)):
            value = json.dumps(value)
        return await redis.set(key,value,ex=expiry)
    
    @check_db
    async def retrieve(self,database:int|str,key:str,redis:Redis=None):
        value = await redis.get(key)
        if not isinstance(value,str):
            return value
        value = json.loads(value)
        return value
    
    @check_db
    async def append(self,database:int|str,key:str,data:Any,redis:Redis=None):
        return await redis.append(key,data)
    
    async def store_bkg_result(self,data,key,expiry):
        if not await self.retrieve(0,key):
            response = await self.store(0,key,[data],expiry)
        else:
            response = await self.append(0,key,data,expiry)
        return response
            
            

@ServiceClass
class TortoiseConnectionService(DatabaseService):

    def __init__(self, configService:ConfigService):
        super().__init__(configService,None)

    def build(self):
        ...
    
    