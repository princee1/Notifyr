import asyncio
import functools
import json
from random import randint
from typing import Any, Callable, Dict, Self
from typing_extensions import Literal
from redis import Redis, ResponseError
from app.classes.broker import MessageBroker, json_to_exception
from app.classes.callbacks import CALLBACKS_CONFIG
from app.definition._service import Service
from app.errors.async_error import ReactiveSubjectNotFoundError
from app.errors.db_error import RedisDatabaseDoesNotExistsError, RedisStreamDoesNotExistsError
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.database.base_db_service import TempCredentialsDatabaseService
from app.services.reactive_service import ReactiveService
from app.services.vault_service import VaultService
from app.utils.constant import RedisConstant, SubConstant, VaultConstant
from app.utils.globals import APP_MODE, ApplicationMode
from app.utils.transformer import none_to_empty_str
from redis.asyncio import Redis
from redis import Redis as SyncRedis


MS_1000 = 1000
ENGINE_KEY = 'engine'
DB_KEY = 'db'



@Service()
class RedisService(TempCredentialsDatabaseService):

    GROUP = 'NOTIFYR-GROUP'
    
    def __init__(self,configService:ConfigService,reactiveService:ReactiveService,vaultService:VaultService,uvicornWorkerService:UvicornWorkerService):
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
        
        return async_wrapper  if APP_MODE == ApplicationMode.server else sync_wrapper
        

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
        host = 'redis'
        self.creds = self.vaultService.database_engine.generate_credentials(VaultConstant.REDIS_ROLE)
        self.backend_creds = self.vaultService.database_engine.generate_credentials(VaultConstant.CELERY_BACKEND_ROLE)
        
        if self.configService.CELERY_BROKER == 'redis':
            self.broker_creds = self.vaultService.database_engine.generate_credentials(VaultConstant.CELERY_BACKEND_ROLE)

        self.redis_celery = Redis(host=self.configService.REDIS_HOST,db=RedisConstant.CELERY_DB,username=self.backend_creds['data']['username'],password=self.backend_creds['data']['password'])
        self.redis_limiter = Redis(host=host,db=RedisConstant.LIMITER_DB,username=self.db_user,password=self.db_password)
        self.redis_cache = Redis(host=host,db=RedisConstant.CACHE_DB,decode_responses=True,username=self.db_user,password=self.db_password)

        if APP_MODE == ApplicationMode.server:
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

    def revoke_lease(self):
        if self.configService.CELERY_BROKER == 'redis':
            self.vaultService.revoke_lease(self.broker_creds['lease_id'])

        self.vaultService.revoke_lease(self.backend_creds['lease_id'])
        return super().revoke_lease()

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
    async def delete_all(self, database: int | str, prefix: str, simple_prefix=True,redis: Redis = None):
        if simple_prefix:
            prefix =f"{prefix}*"
        keys = await self.scan(database,prefix)
        if keys:
            return await redis.delete(*keys)
        return 0
    
    @check_db
    async def scan(self,database:int|str,match,redis:Redis=None):
        cursor = 0
        keys = []
        while True:
            cursor, key = redis.scan(
                cursor=cursor,
                match=match,
                count=500
            )
            keys.extend(key)
            if cursor == 0:
                break
        return list(set(keys))
    
    @check_db
    async def append(self,database:int|str,key:str,data:Any,redis:Redis=None):
        return await redis.append(key,data)
        
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
    async def hash_kdel(self,database:int|str,hash_name,*keys:str,redis:Redis=None):
        return await redis.hdel(*keys)
    
    @check_db
    async def hash_set(self,database:int|str,hash_name:str,key:str=None,value:Any=None,mapping:dict=None,redis:Redis=None):
        redis.hset
        return await redis.hset(hash_name,key,value,mapping)
    
    @check_db
    async def expire(self,database:int|str,hash_name:str,ttl:int,nx=False,redis:Redis=None):
        return await redis.expire(hash_name,ttl,nx=nx)
    
    @check_db
    async def hash_get(self,database:int|str,hash_name,redis:Redis=None):
        return await redis.hgetall(hash_name)
       
    @check_db
    async def push(self,database:int|str,name:str,*element:dict,redis:Redis=None):
        return await redis.lpush(name,*element)

    @check_db
    async def range(self,database:int|str,name:str,start:int,stop:int,redis:Redis=None):
        return await redis.lrange(name,start,stop)

  