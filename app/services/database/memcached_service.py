import functools
import json
from typing import Any, Callable
from app.definition._service import Service
from app.errors.db_error import MemCacheNoValidKeysDefinedError, MemCachedCacheMissError, MemCachedTypeValueError
from app.errors.service_error import BuildFailureError, BuildWarningError
from app.interface.timers import SchedulerInterface
from app.services.config_service import ConfigService
from app.services.database.base_db_service import DatabaseService
from pymemcache import Client as SyncClient,MemcacheClientError,MemcacheServerError,MemcacheUnexpectedCloseError
from aiomcache import Client



@Service()
class MemCachedService(DatabaseService,SchedulerInterface):
    
    DEFAULT_PORT= 11211  
    POOL_MINSIZE=2
    POOL_MAXSIZE =5

    def __init__(self, configService:ConfigService):
        super().__init__(configService, None)
    
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
            raise BuildFailureError(f"Failed to connect to Memcached. {e}")
        
        except MemcacheUnexpectedCloseError as e:
            raise BuildFailureError(f"Failed to connect to Memcached. {e}")
            
        except MemcacheServerError as e:
            raise BuildWarningError(f"Failed to connect to Memcached. {e}")
            
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
