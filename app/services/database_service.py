import functools
from typing import Any, Callable, Dict, Self, TypedDict
import aiohttp
import requests
from typing_extensions import Literal
from random import random,randint
from app.classes.broker import MessageBroker, json_to_exception
from app.definition._error import BaseError
from app.services.reactive_service import ReactiveService
from app.utils.constant import MongooseDBConstant, StreamConstant, SubConstant
from app.utils.transformer import none_to_empty_str
from .config_service import MODE, CeleryMode, ConfigService
from .file_service import FileService
from app.definition._service import BuildFailureError, BaseService,AbstractServiceClass,Service,BuildWarningError, StateProtocol
from motor.motor_asyncio import AsyncIOMotorClient,AsyncIOMotorClientSession,AsyncIOMotorDatabase
from odmantic import AIOEngine
from odmantic.exceptions import BaseEngineException
from redis.asyncio import Redis
from redis import Redis as SyncRedis
from redis.exceptions import ResponseError
import json
import asyncio
from tortoise import Tortoise
from app.errors.async_error import ReactiveSubjectNotFoundError
import psycopg2
from pymongo.errors import ConnectionFailure,ConfigurationError, ServerSelectionTimeoutError
from app.utils.constant import SettingDBConstant

MS_1000 = 1000
ENGINE_KEY = 'engine'
DB_KEY = 'db'


class RedisStreamDoesNotExistsError(BaseError):
    ...

class RedisDatabaseDoesNotExistsError(BaseError):
    ...

@AbstractServiceClass
class DatabaseService(BaseService): 
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
            super().__init__()
            self.configService= configService
            self.fileService = fileService

@Service
class MongooseService(DatabaseService): # Chat data
    COLLECTION_REF = Literal['agent','chat','profile']
    DATABASE_NAME=  MongooseDBConstant.DATABASE_NAME

    #NOTE SEE https://motor.readthedocs.io/en/latest/examples/bulk.html
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__(configService,fileService)
        self.mongo_uri = self.configService.getenv('MONGO_URI')

    async def save(self, model,*args):
        return await self.engine.save(model,*args)
    
    async def find(self,model,*args):
        return await self.engine.find(model,*args)

    async def find_one(self,model,*args):
        return await self.engine.find_one(model,*args)
    
    async def delete(self,model,*args):
        return await self.engine.delete(model,*args)

    async def count(self,model,*args):
        return await self.engine.count(model,*args)
    
    def build(self,build_state=-1):
        try:    

            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.motor_db = AsyncIOMotorDatabase(self.client,self.DATABASE_NAME)
            self.engine = AIOEngine(self.client,self.DATABASE_NAME)

        except ConnectionFailure as e:
            raise BuildFailureError(f"MongoDB connection error: {e}")
        except ConfigurationError as e:
            raise BuildFailureError(f"MongoDB configuration error: {e}")

        except BaseEngineException as e:
            raise BuildFailureError(f"ODMantic engine error: {e}")

        except ServerSelectionTimeoutError as e:
            raise BuildFailureError(f"MongoDB server selection timeout: {e}")

        except Exception as e: # TODO
            print(e) 
            raise BuildFailureError(f"Unexpected error: {e}") 

@Service
class RedisService(DatabaseService):

    class StreamConfig(TypedDict):
        sub:bool
        count:int|None = None
        block:int|None=None
        wait:int|None=None
        stream:bool
        channel_tasks:asyncio.Task | None = None
        stream_tasks: asyncio.Task | None = None


    GROUP = 'NOTIFYR-GROUP'
    
    def __init__(self,configService:ConfigService,reactiveService:ReactiveService):
        super().__init__(configService,None)
        self.configService = configService
        self.reactiveService = reactiveService
        self.to_shutdown = False
        
        self.streams:Dict[StreamConstant.StreamLiteral,RedisService.StreamConfig] = {
            StreamConstant.LINKS_EVENT_STREAM:self.StreamConfig(**{
                'sub':True,
                'count':MS_1000*4,
                'block':MS_1000*5,
                'stream':True
            }),
            StreamConstant.EMAIL_EVENT_STREAM:self.StreamConfig(**{
                'sub':True,
                'count':MS_1000,
                'block':MS_1000*15,
                'wait':70,
                'stream':True
            }),
            StreamConstant.TWILIO_REACTIVE:self.StreamConfig(**{
                'sub':True,
                'stream':False}),
            
            StreamConstant.EMAIL_TRACKING:self.StreamConfig(**{
                'sub':False,
                'stream':True,
                'block':MS_1000*2,
                'wait':5,
            }),

            StreamConstant.TWILIO_TRACKING_CALL:self.StreamConfig(
                sub=False,
                stream=True,
                wait=5,
                block=MS_1000*5
            ),
            StreamConstant.TWILIO_TRACKING_SMS:self.StreamConfig(
                sub=False,
                stream=True,
                wait=5,
                block=MS_1000*5
            ),
            StreamConstant.TWILIO_EVENT_STREAM_CALL:self.StreamConfig(
                sub=True,
                stream=True,
                wait=45,
                block=MS_1000*15,
                count=MS_1000*5,

            ),
            StreamConstant.TWILIO_EVENT_STREAM_SMS:self.StreamConfig(
                sub=True,
                stream=True,
                wait=45,
                block=MS_1000*15,
                count=500,
            ),
            StreamConstant.CONTACT_CREATION_EVENT:self.StreamConfig(
                sub=False,
                stream=True,
                wait = 60*60*6,
                block=MS_1000*10,
                count=1000
            ),
            StreamConstant.CONTACT_SUBS_EVENT:self.StreamConfig(
                sub=False,
                stream=True,
                wait = 60*60*4,
                block=MS_1000*20,
                count=10000
            ),
            StreamConstant.CELERY_RETRY_MECHANISM:self.StreamConfig(
                sub=False,
                stream=True,
                wait=10,
                block=10,
                count=1000,
            ),

            SubConstant.SERVICE_STATUS:self.StreamConfig(
                sub=True,
                stream=False
            )
        }

        self.consumer_name = f'notifyr-consumer={self.configService.INSTANCE_ID}'


    def dynamic_context(func:Callable):
        
        async def async_wrapper(self:Self,topic:str,data:Any|dict):
            await func(self,topic,data)
        
        def sync_wrapper(self:Self,topic:str,data:Any|dict):
            return func(self,topic,data)
        
        return async_wrapper  if ConfigService._celery_env == CeleryMode.none else sync_wrapper
        

    @dynamic_context
    def stream_data(self,stream:str,data:dict):
        if stream not in self.streams.keys():
            raise RedisStreamDoesNotExistsError(stream)
        
        if not isinstance(data,dict):
            return 
        
        if not data:
            return 
        none_to_empty_str(data)
        return self.redis_events.xadd(stream,data)

    @dynamic_context
    def publish_data(self,channel:str,data:Any):
        if channel not in self.streams.keys():
            return
        #if data:   
        data = json.dumps(data)
        return self.redis_events.publish(channel,data)
        
    async def _consume_channel(self,channels,handler:Callable[[Any],MessageBroker|Any|None]):
        pubsub = self.redis_events.pubsub()

        if channels != SubConstant.SERVICE_STATUS:
            def handler_wrapper(message):
                if message is None:
                    print('No message')
                    return
                if message["type"] == "message":
                    try:
                        message_broker = json.loads(message["data"])
                        message_broker = MessageBroker(**message_broker)

                        if handler != None:
                            handler(message_broker)
                        subject_id = message_broker['subject_id']
                        state = message_broker['state']
                        value = message_broker['value']
                        error = message_broker['error']
                        subject = self.reactiveService[subject_id]
                        match state:
                            case 'completed':
                                self.reactiveService.delete_subject(subject_id)
                            case 'error':
                                error  = json_to_exception(error)
                                subject.on_error(error)
                            case 'next':
                                subject.on_next(value)
                                                                
                    except json.JSONDecodeError:
                        print(f"[Handler] Bad JSON: {message['data']}")
                    except ReactiveSubjectNotFoundError:
                        ...
        else:
            async def handler_wrapper(message):
                if 'data' not in message: 
                    return
                data= json.loads(message["data"])
                if asyncio.iscoroutinefunction(handler):
                    return await handler(data)
                return handler(data)

        await pubsub.subscribe(**{channels:handler_wrapper}) # TODO Maybe add the function as await

        while True:
            await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
            await asyncio.sleep(0.01)
            if self.to_shutdown:
                return

    async def create_group(self):

        for stream in self.streams.keys():
            try:
                await self.redis_events.xgroup_create(stream, RedisService.GROUP, id='0-0', mkstream=True)
            except ResponseError as e:
                if "BUSYGROUP" in str(e):
                    ...
                else:
                    ...

    def register_consumer(self,callbacks_sub:dict[str,Callable]={},callbacks_stream:dict[str,Callable]={}):
        for stream_name,config in self.streams.items():
            is_stream = config['stream']
            is_sub = config['sub']
            if is_stream:
                count = config.get('count',MS_1000)
                block = config.get('block',MS_1000)
                wait = config.get('wait',60)
            config.update ({
                'channel_tasks':None,
                'stream_tasks':None
            })

            if is_sub:
                channel_callback = callbacks_sub.get(stream_name,lambda v:print(v))# Print later
                config['channel_tasks']= asyncio.create_task(self._consume_channel(stream_name,channel_callback))
            
            if is_stream:
                stream_callback = callbacks_stream.get(stream_name,None)
                config['stream_tasks'] =asyncio.create_task(self._consume_stream(stream_name,count,block,wait,stream_callback))           

    async def _consume_stream(self,stream_name,count,block,wait,handler:Callable[[dict[str,Any]],list]):
        while True:
            await asyncio.sleep(wait+(randint(10,50)))
            try:
                response = await self.redis_events.xreadgroup(self.GROUP,self.consumer_name, {stream_name: '>'}, count=count, block=block)
                if response:
                    for stream, entries in response:
                        entry_ids = await handler(entries)
                        await self.redis_events.xack(stream_name, self.GROUP, *entry_ids)
                        await self.redis_events.xdel(stream_name,*entry_ids )
            except:
                ...
            finally:
                if self.to_shutdown:
                    return

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

    def build(self,build_state=-1):
        host = self.configService.REDIS_URL
        host = "localhost"
        self.redis_celery = Redis(host=host,db=0)
        self.redis_limiter = Redis(host=host,db=1)
        self.redis_cache = Redis(host=host,db=3,decode_responses=True)

        if self.configService.celery_env == CeleryMode.none:
            self.redis_events=Redis(host=host,db=2,decode_responses=True)
        else :
            self.redis_events = SyncRedis(host=host,db=2,decode_responses=True)

        self.db:Dict[Literal['celery','limiter','events','cache',0,1,2,3],Redis] = {
            0:self.redis_celery,
            1:self.redis_limiter,
            2:self.redis_events,
            3:self.redis_cache,
            'celery':self.redis_celery,
            'limiter':self.redis_limiter,
            'events': self.redis_events,
            'cache':self.redis_cache,
        }

        try:
            temp_redis = SyncRedis(host=host)
            pong = temp_redis.ping()
            if not pong:
                raise ConnectionError("Redis ping failed")
            temp_redis.close()
        except Exception as e:
            raise BuildFailureError(e.args)
 
    @check_db
    async def store(self,database:int|str,key:str,value:Any,expiry,nx:bool= False,xx:bool=False,redis:Redis=None):
        if isinstance(value,(dict,list)):
            value = json.dumps(value)
        if expiry <=0:
            expiry = None
        return await redis.set(key,value,ex=expiry,get=True,nx=nx,xx=xx)
    
    @check_db
    async def retrieve(self,database:int|str,key:str,redis:Redis=None):
        value = await redis.get(key)
        if not isinstance(value,str):
            return value
        value = json.loads(value)
        return value
    
    @check_db
    async def delete(self,database:int|str,key:str,redis:Redis=None):
        return await redis.delete(key)

    @check_db
    async def exists(self,database:int|str,key:str,redis:Redis=None)->bool:
        if isinstance(key,(list,tuple)):
            result =  await redis.exists(*key)
        elif isinstance(key,dict):
            result = await redis.exists(*key.keys())
        else:
            result =  await redis.exists(key)
        
        return result > 0
            
    @check_db
    async def delete_all(self, database: int | str, prefix: str,simple_prefix=True, redis: Redis = None):
        if simple_prefix:
            prefix =f"{prefix}*"
        keys = await redis.keys(prefix)
        if keys:
            return await redis.delete(*keys)
        return 0
    
    @check_db
    async def append(self,database:int|str,key:str,data:Any,redis:Redis=None):
        return await redis.append(key,data)
    
    async def store_bkg_result(self,data,key,expiry):
        if not await self.retrieve(0,key):
            response = await self.store(0,key,[data],expiry)
        else:
            response = await self.append(0,key,data,expiry)
        return response
        
    async def close_connections(self,):
        for config in self.streams.values():
            if 'channel_tasks' in config and  config['channel_tasks']:
                config['channel_tasks'].cancel()
            if 'stream_tasks' in config and config['stream_tasks']:
                config['stream_tasks'].cancel()
            
        len_db = len(self.db.keys())//2
        for i in range(len_db):
            await self.db[i].close()
            
@Service
class TortoiseConnectionService(DatabaseService):
    DATABASE_NAME = 'notifyr'

    def __init__(self, configService: ConfigService):
        super().__init__(configService, None)


    def verify_dependency(self):
        pg_user = self.configService.getenv('POSTGRES_USER')
        pg_password = self.configService.getenv('POSTGRES_PASSWORD')

        if not pg_user or not pg_password:
            raise BuildFailureError

    def build(self,build_state=-1):
        try:
            pg_user = self.configService.getenv('POSTGRES_USER')
            pg_password = self.configService.getenv('POSTGRES_PASSWORD')

            pg_host ='0.0.0.0' if  self.configService.MODE == MODE.PROD_MODE else 'localhost'
            conn = psycopg2.connect(
                dbname=self.DATABASE_NAME,
                user=pg_user,
                password=pg_password,
                host=pg_host,
                port=5432
            )
        except Exception as e:
            raise BuildFailureError(f"Error during Tortoise ORM connection: {e}")

        finally:
            try:
                if conn:
                    conn.close()
            except:
                ...
    
@Service  
class JSONServerDBService(DatabaseService):
    
    def __init__(self,configService:ConfigService,fileService:FileService,redisService:RedisService):
        super().__init__(configService, fileService)
        self.json_server_url = configService.SETTING_DB_URL
        self.redisService = redisService
    
    def build(self,build_state=-1):
        try:
            response = requests.get(f"{self.json_server_url}/health",timeout=1)
            if response.json()["status"] == "ok":
                ...
            else:
                raise BuildFailureError

        except TimeoutError:
            raise BuildWarningError

        except requests.RequestException:
            raise BuildFailureError

        except KeyError:
            raise BuildWarningError
    

    def get_setting(self)->dict:
        try:
        
            response=  requests.get(f"{self.json_server_url}/{SettingDBConstant.BASE_JSON_DB}")
            if response.status_code == 200:
                return response.json()
            else:
                raise BuildWarningError(f"Error fetching data: {response.status_code}")
        except:
            raise BuildWarningError("Error connecting to JSON server")

    async def aio_get_setting(self)->dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.json_server_url}/{SettingDBConstant.BASE_JSON_DB}") as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            self.redisService.publish_data(SubConstant.SERVICE_STATUS,StateProtocol(service=self.name,to_build=True,bypass_async_verify=True,force_sync_verify=True))
            print("Error connecting to JSON server while getting settings")

    async def save_settings(self,data:Any):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(f"{self.json_server_url}/{SettingDBConstant.BASE_JSON_DB}",json=data) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        ...
        except Exception:
            self.redisService.publish_data(SubConstant.SERVICE_STATUS,StateProtocol(service=self.name,to_build=True,bypass_async_verify=True,force_sync_verify=True))
            print("Error connecting to JSON server while saving settings")


