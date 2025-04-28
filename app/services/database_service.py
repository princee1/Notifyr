import functools
from typing import Any, Callable, Dict
from typing_extensions import Literal

from app.definition._error import BaseError
from app.services.reactive_service import ReactiveService
from .config_service import ConfigService
from .file_service import FileService
from app.definition._service import Service,AbstractServiceClass,ServiceClass,BuildWarningError
import sqlite3
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient,AsyncIOMotorClientSession,AsyncIOMotorDatabase
from odmantic import AIOEngine
from redis.asyncio import Redis
from redis.exceptions import ResponseError
import json
import asyncio


class RedisStreamDoesNotExistsError(BaseError):
    ...

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
        except Exception as e: # TODO
            print(e) 
            raise ...    

@ServiceClass
class RedisService(DatabaseService):

    GROUP = 'NOTIFYR-GROUP'
    
    def __init__(self,configService:ConfigService,reactiveService:ReactiveService):
        super().__init__(configService,None)
        self.configService = configService
        self.reactiveService = reactiveService
        
        self.streams = {
            'links':{
                'count':100,
                'wait':5000,
            }
        }

        self.consumer_name = f'notifyr-consumer={self.configService.INSTANCE_ID}'

    async def stream_data(self,stream:str,data:Any):
        if stream not in self.streams.keys():
            raise RedisStreamDoesNotExistsError(stream)
        
        await self.redis_events.xadd(stream,data)

    async def publish_data(self,channel:str,data:Any):
        data = json.dumps(data)
        return await self.redis_events.publish(channel,data)
    
    async def _consume_channel(self,channels,handler:Callable[[Any],Any]):
        pubsub = self.redis_events.pubsub()

        def handler_wrapper(message):
            if message is None:
                return
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    return handler(data)
                except json.JSONDecodeError:
                    print(f"[Handler] Bad JSON: {message['data']}")

        await pubsub.subscribe(channels)

        while True:
            await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
            await asyncio.sleep(0.01)

    async def create_group(self):

        for stream in self.streams.keys():
            try:
                await self.redis_events.xgroup_create(stream, RedisService.GROUP, id='0-0', mkstream=True)
            except ResponseError as e:
                if "BUSYGROUP" in str(e):
                    print("Group already exists")
                else:
                    ...

    def register_stream_consumer(self):
        for stream_name,config in self.streams.items():
            count = config['count']
            wait = config['wait']
            asyncio.create_task(self._consume_stream(stream_name,count,wait))

    async def _consume_stream(self,stream_name,count,wait):
        while True:
            try:
                response = await self.redis_events.xreadgroup(RedisService.GROUP,self.consumer_name, {stream_name: '>'}, count=count, block=wait)
                if response:
                    for stream, entries in response:
                        for entry_id, data in entries:

                            print(entry_id,data)
                            await self.redis_events.xack(stream_name, RedisService.GROUP, entry_id)
                            await self.redis_events.xdel(stream_name, entry_id)
            except:
                ...

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
        self.redis_events=Redis(host=host,db=2,decode_responses=True)
        self.db:Dict[Literal['celery','limiter','events',0,1,2],Redis] = {
            0:self.redis_celery,
            1:self.redis_limiter,
            2:self.redis_events,
            #2:self.redis_cache,
            'celery':self.redis_celery,
            'limiter':self.redis_limiter,
            'events': self.redis_events
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
    
    