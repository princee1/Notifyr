import functools
import time
from typing import Any, Callable, Dict, List, Self, Type, TypeVar, TypedDict
from urllib.parse import urlencode
from beanie import Document, PydanticObjectId, init_beanie
import hvac
import pika
from typing_extensions import Literal
from random import random,randint
from app.classes.callbacks import CALLBACKS_CONFIG
from app.classes.broker import MessageBroker, json_to_exception
from app.classes.vault_engine import VaultDatabaseCredentials
from app.definition._error import BaseError
from app.definition._interface import Interface, IsInterface
from app.interface.timers import IntervalInterface, IntervalParams, SchedulerInterface
from app.services.reactive_service import ReactiveService
from app.services.secret_service import HCVaultService
from app.utils.constant import MongooseDBConstant, RabbitMQConstant, RedisConstant, StreamConstant, SubConstant, VaultConstant, VaultTTLSyncConstant
from app.utils.helper import quote_safe_url, reverseDict, subset_model
from app.utils.transformer import none_to_empty_str
from .config_service import MODE, CeleryMode, ConfigService, UvicornWorkerService
from .file_service import FileService
from app.definition._service import DEFAULT_BUILD_STATE, STATUS_TO_ERROR_MAP, BuildFailureError, BaseService,AbstractServiceClass, LinkDep,Service,BuildWarningError, ServiceNotAvailableError, ServiceStatus, ServiceTemporaryNotAvailableError, StateProtocol
from motor.motor_asyncio import AsyncIOMotorClient
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
from random import randint,random
from app.models.communication_model import *
from app.errors.db_error import *
from pymongo import MongoClient
from pymemcache import Client as SyncClient,MemcacheClientError,MemcacheServerError,MemcacheUnexpectedCloseError
from aiomcache import Client

MS_1000 = 1000
ENGINE_KEY = 'engine'
DB_KEY = 'db'


@AbstractServiceClass()
class DatabaseService(BaseService): 
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        BaseService.__init__(self)
        self.configService= configService
        self.fileService = fileService

@AbstractServiceClass()
class TempCredentialsDatabaseService(DatabaseService,SchedulerInterface):

    def __init__(self,configService:ConfigService,fileService:FileService,vaultService:HCVaultService,ttl,max_retry=2,wait_time=2,t:Literal['constant','linear']='constant',b=0):
        DatabaseService.__init__(self,configService,fileService)
        SchedulerInterface.__init__(self,replace_existing=True,thread_pool_count=1)
        self.vaultService = vaultService
        self.creds:VaultDatabaseCredentials = {}
        self.max_retry = max_retry
        self.wait_time = wait_time
        self.t=t
        self.b = b
        self.last_rotated = None
        self.auth_ttl = ttl

    def build(self, build_state = ...):
        delay = IntervalParams( seconds=self.random_buffer_interval(self.auth_ttl) )
        self.interval_schedule(delay, self.creds_rotation,tuple(),{},f"{self.name}-creds_rotation")

    def verify_dependency(self):
        if self.vaultService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError("Vault Service can’t issue creds")

    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):
        self.check_auth()
        await super().pingService(infinite_wait,data,profile,as_manager,**kwargs)
             
    @staticmethod
    def random_buffer_interval(ttl):
        return ttl - (ttl*.08*random() + randint(20,40))

    def renew_db_creds(self):
        lease_id = self.creds['lease_id']
        self.vaultService.renew_lease(lease_id,3600)
    
    @property
    def db_user(self):
        return self.creds.get('data',dict()).get('username',None)
        
    @property
    def db_password(self):
        return self.creds.get('data',dict()).get('password',None)

    @property
    def lease_id(self):
        return self.creds.get('lease_id',None)
    
    def revoke_lease(self):
        return self.vaultService.revoke_lease(self.lease_id)

    async def _check_vault_status(self):
        temp_service = None 
        async with self.vaultService.statusLock.reader:
            if self.vaultService.service_status == ServiceStatus.AVAILABLE:
                ...
            else: 
                temp_service = self.vaultService.service_status
        return temp_service

    async def creds_rotation(self):
        temp_service = await self._check_vault_status()
        async with self.statusLock.writer:

            retry =0
            while retry<self.max_retry:
                try:
                    if temp_service == None:
                        await self._creds_rotator()
                        self.last_rotated=time.time()
                    else:
                        self.service_status = temp_service
                    break
                except hvac.exceptions.Forbidden:
                    if self.t == 'constant':
                        await asyncio.sleep(self.wait_time)
                    else:
                        await asyncio.sleep( (retry+1)*self.wait_time +self.b)
                
                retry+=1                  

    async def _creds_rotator(self):
        pass

    def check_auth(self):
        if not self.is_connected:
            raise ServiceTemporaryNotAvailableError
        
    @property
    def is_connected(self):
        if self.last_rotated == None:
            return True
        
        return  time.time() - self.last_rotated < self.auth_ttl    

@Service()
class RedisService(TempCredentialsDatabaseService):

    GROUP = 'NOTIFYR-GROUP'
    
    def __init__(self,configService:ConfigService,reactiveService:ReactiveService,vaultService:HCVaultService,uvicornWorkerService:UvicornWorkerService):
        super().__init__(configService,None,vaultService,60*60*24*29,)
        self.configService = configService
        self.reactiveService = reactiveService
        self.uvicornWorkerService = uvicornWorkerService
        self.to_shutdown = False
        self.callbacks = CALLBACKS_CONFIG.copy()

        self.consumer_name = f'notifyr-consumer={self.uvicornWorkerService.INSTANCE_ID}'


    def dynamic_context(func:Callable):
        
        async def async_wrapper(self:Self,topic:str,data:Any|dict):
            return await func(self,topic,data)
        
        def sync_wrapper(self:Self,topic:str,data:Any|dict):
            return func(self,topic,data)
        
        return async_wrapper  if ConfigService._celery_env == CeleryMode.none else sync_wrapper
        

    @dynamic_context
    def stream_data(self,stream:str,data:dict):
        if stream not in self.callbacks.keys():
            raise RedisStreamDoesNotExistsError(stream)
        
        if not isinstance(data,dict):
            return 
        
        if not data:
            return 
        none_to_empty_str(data)
        return self.redis_events.xadd(stream,data)

    @dynamic_context
    def publish_data(self,channel:str,data:Any):
        if channel not in self.callbacks.keys():
            return
        #if data:   
        data = json.dumps(data)
        return self.redis_events.publish(channel,data)
        
    async def _consume_channel(self,channels,handler:Callable[[Any],MessageBroker|Any|None]):
        pubsub = self.redis_events.pubsub()

        if channels not in SubConstant._SUB_CALLBACK:
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
                try:
                    
                    if 'data' not in message: 
                        return
                    data= json.loads(message["data"])
                    if asyncio.iscoroutinefunction(handler):
                        return await handler(data)
                    return handler(data)
                except Exception as e:
                    print(e)
                    print(e.__class__)
                    

        await pubsub.subscribe(**{channels:handler_wrapper}) # TODO Maybe add the function as await

        while True:
            await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
            await asyncio.sleep(0.01)
            if self.to_shutdown:
                return

    async def create_group(self):

        for stream in self.callbacks.keys():
            try:
                await self.redis_events.xgroup_create(stream, RedisService.GROUP, id='0-0', mkstream=True)
            except ResponseError as e:
                if "BUSYGROUP" in str(e):
                    ...
                else:
                    ...

    def register_consumer(self,callbacks_sub:dict[str,Callable]={},callbacks_stream:dict[str,Callable]={}):
        for stream_name,config in self.callbacks.items():
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
        host = self.configService.REDIS_HOST
        self.creds = self.vaultService.database_engine.generate_credentials(VaultConstant.REDIS_ROLE)

        self.redis_celery = Redis(host=host,db=RedisConstant.CELERY_DB,username=self.db_user,password=self.db_password)
        self.redis_limiter = Redis(host=host,db=RedisConstant.LIMITER_DB,username=self.db_user,password=self.db_password)
        self.redis_cache = Redis(host=host,db=RedisConstant.CACHE_DB,decode_responses=True,username=self.db_user,password=self.db_password)

        if self.configService.celery_env == CeleryMode.none:
            self.redis_events=Redis(host=host,db=RedisConstant.EVENT_DB,decode_responses=True,username=self.db_user,password=self.db_password)
        else :
            self.redis_events = SyncRedis(host=host,db=RedisConstant.EVENT_DB,decode_responses=True,username=self.db_user,password=self.db_password)
        
        super().build()

        self.db:Dict[Literal['celery','limiter','events','cache',0,1,2,3],Redis] = {
            RedisConstant.CELERY_DB:self.redis_celery,
            RedisConstant.LIMITER_DB:self.redis_limiter,
            RedisConstant.EVENT_DB:self.redis_events,
            RedisConstant.CACHE_DB:self.redis_cache,
            'celery':self.redis_celery,
            'limiter':self.redis_limiter,
            'events': self.redis_events,
            'cache':self.redis_cache,
        }

        try:
            temp_redis = SyncRedis(host=host,password=self.db_password,username=self.db_user)
            pong = temp_redis.ping()
            if not pong:
                raise ConnectionError("Redis ping failed")
            temp_redis.close()
        except Exception as e:
            print(e)
            print(e.args)
            print(e.__class__)
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
        for config in self.callbacks.values():
            if 'channel_tasks' in config and  config['channel_tasks']:
                config['channel_tasks'].cancel()
            if 'stream_tasks' in config and config['stream_tasks']:
                config['stream_tasks'].cancel()
            
        len_db = len(self.db.keys())//2
        for i in range(len_db):
            await self.db[i].close()

    @check_db
    async def increment(self,database:int|str,name:str,amount:int,redis:Redis=None):
        return await redis.incrby(name,amount)
    
    @check_db
    async def decrement(self,database:int|str,name:str,amount:int,redis:Redis=None):
        return await redis.decrby(name,amount)

    @check_db
    async def hash_iter(self,database:int|str,hash_name:str,iter=False,match:str=None,count=None,redis:Redis=None):
        if iter:
            return await redis.hscan_iter(hash_name,match,count)
        else:
            return await redis.hgetall(hash_name)
    
    @check_db
    async def hash_del(self,database:int|str,hash_name,*keys:str,redis:Redis=None):
        return await redis.hdel(*keys)

    @check_db
    async def push(self,database:int|str,name:str,*element:dict,redis:Redis=None):
        return await redis.lpush(name,*element)

    @check_db
    async def range(self,database:int|str,name:str,start:int,stop:int,redis:Redis=None):
        return await redis.lrange(name,start,stop)

    
@Service()
class MemCachedService(DatabaseService,SchedulerInterface):
    
    DEFAULT_PORT= 11211  
    POOL_MINSIZE=2
    POOL_MAXSIZE =5

    def __init__(self, configService:ConfigService, fileService:FileService):
        super().__init__(configService, fileService)
    
    @staticmethod
    def KeyEncoder(func:Callable):

        @functools.wraps(func)
        async def wrapper(self,key:str,*args,**kwargs):
            if type(key)== str:
                key = key.encode()
            return await func(self,key,*args,**kwargs)

        return wrapper
    
    def build(self, build_state = ...):
        try:
            self.sync_client = SyncClient((self.configService.MEMCACHED_HOST,self.DEFAULT_PORT),connect_timeout=6)
            self.client = Client(self.configService.MEMCACHED_HOST,pool_minsize=self.POOL_MINSIZE,pool_size=self.POOL_MAXSIZE)
            version = self.sync_client.version().decode()
           
        except MemcacheClientError as e:
            raise BuildFailureError
        
        except MemcacheUnexpectedCloseError as e:
            raise BuildFailureError
            
        except MemcacheServerError as e:
            raise BuildWarningError
            
    @KeyEncoder
    async def get(self,key:str,default:Any=None,_raise=False,_return_bytes=False)->Any|bytes:
        result = await self.client.get(key,None)
        if result == None and default != None:
            if _raise:
                raise MemCachedCacheMissError
            else: return default
    
        return json.loads(result) if result!=None and not _return_bytes else result
   
    async def delete(self,*key:str):
        if len(key) < 1:
            raise MemCacheNoValidKeysDefinedError('Key not given')
        
        if len(key)==1:
            key = key.encode()
            return await self.client.delete(key)

        return self.sync_client.delete_many(list(key))
    
    @KeyEncoder
    async def set(self,key:str,value:Any|bytes,expire:int=0,multi=False):     
        if not multi:
            if type(value) != bytes:
                value = json.dumps(value).encode()
            return await self.client.set(key,value,expire)
        
        if type(value) != dict:
            raise MemCachedTypeValueError('Must be a dict')
        return self.sync_client.set_many(value,expire)
        
    @KeyEncoder
    async def exist(self,key:str):
        return self.get(key,None,False) != None

    async def clear(self):
        await self.client.flush_all()
    
    async def close(self):
        self.sync_client.close()
        self.client.close()

D = TypeVar('D',bound=Document)

@Service(links=[LinkDep(HCVaultService,to_build=True,to_destroy=True)])     
class MongooseService(TempCredentialsDatabaseService):
    COLLECTION_REF = Literal["agent", "chat", "profile"]
    DATABASE_NAME = MongooseDBConstant.DATABASE_NAME

    def __init__(
        self,
        configService: ConfigService,
        fileService: FileService,
        vaultService: HCVaultService,
    ):
        super().__init__(configService, fileService,vaultService,VaultTTLSyncConstant.MONGODB_AUTH_TTL)

        self.client: AsyncIOMotorClient | None = None
        self._documents = []
        self.mongoConstant = MongooseDBConstant()

    ##################################################
    # CRUD-like API (Beanie style)
    ##################################################
    async def insert(self,model:Document,*args,**kwargs):
        return await model.insert(*args, **kwargs)

    async def get(self,model:Type[D],id:str,raise_:bool = True)->D:
        m = await model.get(PydanticObjectId(id))
        if m == None and raise_:
            raise DocumentDoesNotExistsError(id)
        return m
    
    async def find_all(self,model:Type[D])->List[D]:
        return await model.find_all().to_list()

    async def find(self, model: Type[D], *args, **kwargs):
        return await model.find(*args, **kwargs).to_list()

    async def find_one(self, model: Type[D], *args, **kwargs):
        return await model.find_one(*args, **kwargs)

    async def delete(self, model: D, *args, **kwargs):
        return await model.delete(*args, **kwargs)

    async def delete_all(self,model:Type[D],*args,**kwargs):
        return await model.delete_all(*args,**kwargs)

    async def count(self, model: Type[D], *args, **kwargs):
        return await model.find(*args, **kwargs).count()
    
    async def primary_key_constraint(self,model:D,raise_when:bool = None):
        pk_field = getattr(model,'_primary_key',None)
        if not pk_field:
            return
        
        pk_value = getattr(model,pk_field,None)
        if pk_value == None:
            return
        
        params = {pk_field:pk_value}
        is_exist= (await self.find_one(model.__class__,params) != None)
        if raise_when != None:
            if (raise_when and is_exist) or (not raise_when and not is_exist):
                raise DocumentPrimaryKeyConflictError(pk_value=pk_value,model=model.__class__,pk_field=pk_field)
        else:
            return is_exist

    async def exists_unique(self,model:D,raise_when:bool = None):
        unique_indexes = getattr(model,'unique_indexes',None)
        if unique_indexes == None:
            return False
        
        params = {i:getattr(model,i,None)  for i in unique_indexes }
        is_exist= (await self.find_one(model.__class__,params) != None)
        if raise_when != None:
            if (raise_when and is_exist) or (not raise_when and not is_exist):
                raise DocumentExistsUniqueConstraintError(exists=is_exist,model=model.__class__,params=params)
        else:
            return is_exist

    def sync_find(self,collection:str,model:Type[D],filter={},projection:dict={},return_model=False)->list[D]:
        
        filter['_class_id'] = {"$regex": f"{model.__name__}$" }
    
        if collection not in self.mongoConstant.available_collection:
            raise MongoCollectionDoesNotExists(collection)

        mongo_collection = self.sync_db[collection]
        docs= mongo_collection.find(filter,projection).to_list()
        return docs if not return_model else [model.model_construct(**doc) for doc in docs]
       
    ##################################################
    # Service lifecycle
    ##################################################

    def build(self, build_state=DEFAULT_BUILD_STATE):
        try:
            self.db_connection()
            super().build()
        except ConnectionFailure as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB connection error: {e}")

        except ConfigurationError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB configuration error: {e}")

        except ServerSelectionTimeoutError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB server selection timeout: {e}")

        except Exception as e:
            print(e)
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"Unexpected error: {e}")

    def db_connection(self):
        # fetch fresh creds from Vault
        self.creds = self.vaultService.database_engine.generate_credentials(VaultConstant.MONGO_ROLE)
        
        self.sync_client = MongoClient(self.mongo_uri)
        self.sync_db = self.sync_client[self.DATABASE_NAME]

        self.client = AsyncIOMotorClient(self.mongo_uri)
        self.motor_db = self.client[self.DATABASE_NAME]

    async def _creds_rotator(self):
        self.close_connection()
        self.db_connection()
        await self.init_connection()

    def close_connection(self):
        try:
            self.client.close()
            self.sync_client.close()
        except Exception as e:
            ...

    async def init_connection(self,):
        await init_beanie(
                database=self.motor_db,
                document_models=self._documents,
            )
        
    def register_document(self,*documents):
        temp = set()
        temp.update(self._documents)
        temp.update(list(documents))
        self._documents = list(temp)


    ##################################################
    # Connection string
    ##################################################
    @property
    def mongo_uri(self):
        return f"mongodb://{self.db_user}:{self.db_password}@{self.configService.MONGO_HOST}:27017/{self.DATABASE_NAME}"
        
    ##################################################
    # Healthcheck
    ##################################################
    
    def destroy(self, destroy_state = ...):
        self.close_connection()
    
@Service(links=[LinkDep(HCVaultService,to_build=True,to_destroy=True)])
class TortoiseConnectionService(TempCredentialsDatabaseService):
    DATABASE_NAME = 'notifyr'

    def __init__(self, configService: ConfigService,vaultService:HCVaultService):
        super().__init__(configService, None,vaultService,VaultTTLSyncConstant.POSTGRES_AUTH_TTL)

    def build(self,build_state=-1):
        try:
            self.generate_creds()
            conn = psycopg2.connect(
                dbname=self.DATABASE_NAME,
                user=self.db_user,
                password=self.db_password,
                host=self.configService.POSTGRES_HOST,
                port=5432
            )
            super().build()
        except Exception as e:
            raise BuildFailureError(f"Error during Tortoise ORM connection: {e}")

        finally:
            try:
                if conn:
                    conn.close()
            except:
                ...

    def generate_creds(self):
        self.creds = self.vaultService.database_engine.generate_credentials(VaultConstant.POSTGRES_ROLE)
        
    @property
    def postgres_uri(self):
        return f"postgres://{self.db_user}:{self.db_password}@{self.configService.POSTGRES_HOST}:5432/{self.DATABASE_NAME}"
        
    async def init_connection(self,close=False):
        if close:
            await self.close_connections()
        await Tortoise.init(
            db_url=self.postgres_uri,
            modules={"models": ["app.models.contacts_model","app.models.security_model","app.models.email_model","app.models.link_model","app.models.twilio_model"]},
        )

    async def close_connections(self):
        await Tortoise.close_connections()    

    async def _creds_rotator(self):
        self.generate_creds()
        await self.init_connection(True)

@Service(links=[LinkDep(HCVaultService,to_build=True,to_destroy=True)]) 
class RabbitMQService(TempCredentialsDatabaseService):
    
    def __init__(self, configService:ConfigService, fileService:FileService, vaultService:HCVaultService):
        super().__init__(configService, fileService, vaultService, 60*60*24*29)
    
    def build(self, build_state = ...):
        
        self.creds=self.vaultService.rabbitmq_engine.generate_credentials()
        credentials = pika.PlainCredentials(username=self.db_user,password=self.db_password)

        params = pika.ConnectionParameters(
            host=self.configService.RABBITMQ_HOST,
            port=5672,
            virtual_host=RabbitMQConstant.CELERY_VIRTUAL_HOST,
            credentials=credentials,
            connection_attempts=1,      # don’t retry
            socket_timeout=5,           # 5 second timeout
            blocked_connection_timeout=5,
        )

        try:
            connection = pika.BlockingConnection(params)
            connection.close()
            super().build()

        except Exception as e:
            print(e)
            print(e.__class__)
            print(e.args)
            self.configService.CELERY_BROKER = 'redis'
            raise BuildFailureError
    