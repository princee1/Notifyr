from functools import wraps
from typing import Dict, Generic, Type, TypeVar, TypedDict
from aiohttp_retry import Any, Callable
from pydantic import BaseModel
from app.classes.minio import ObjectS3ResponseModel, key_setter
from app.container import Get
from app.services.database_service import MemCachedService,MemCacheNoValidKeysDefinedError
from pydantic.main import _model_construction

from app.utils.helper import APIFilterInject

C = TypeVar('C',BaseModel,Dict,dict,bool,int,str)

memcachedService:MemCachedService = Get(MemCachedService)

class ResponseCacheInterface(Generic[C]):

    @staticmethod
    async def Get(key:str)->Any:
        ...

    @staticmethod
    async def Delete(key:str)->bool:
        ...
    
    @staticmethod
    async def Set(key:str,value:Any)->bool:
        ...    
    
def generate_cache_type(_type:Type[C],prefix:str,sep="/",key_builder:Callable[...,str]=None,default_expiry=3600,in_memory_size=-1,_raise_miss=False,multi=False)->Type[ResponseCacheInterface[C]]:
    if default_expiry < 0:
        default_expiry = 0

    json_type = {dict,Dict,TypedDict,BaseModel}
    def key_builder_decorator(func:Callable):
        @wraps(func)
        async def wrapper(*args,**kwargs):
            if key_builder:
                # k= kwargs.copy()
                # k['key'] = key
                key = APIFilterInject(key_builder)(**kwargs)
            else:
                key = args[0]
            
            if not isinstance(key,str):
                raise MemCacheNoValidKeysDefinedError

            key= f"{prefix}{sep}{key}"
            return await func(key,*args)
    
        return wrapper


    class ResCache(ResponseCacheInterface):
        
        @staticmethod
        @key_builder_decorator
        async def Get(key:str)->C|None:
            result:Any |None = await memcachedService.get(key,None,_raise_miss)
            if result == None:
                print('CACHE MISS -','Key:',key)
                return None
            
            if _type in json_type: 
                if type(_type) ==_model_construction.ModelMetaclass:
                    result = _type.model_construct(**result)
                else:
                    result = _type(**result)
            print('CACHE HIT -','Key:',key)
            return result
                

        @staticmethod
        @key_builder_decorator
        async def Set(key:str,value:C,expiry=default_expiry):
            if type(_type) ==_model_construction.ModelMetaclass and isinstance(value,BaseModel):
                value = value.model_dump('json')        
            return await memcachedService.set(key,value,expiry,multi)

        @staticmethod
        @key_builder_decorator
        async def Delete(key:str):
            return await memcachedService.delete(key)
    
    return ResCache


MinioResponseCache = generate_cache_type(ObjectS3ResponseModel,'object',key_builder=key_setter)
BlogResponseCache = generate_cache_type(dict,'blog',)