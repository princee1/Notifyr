import functools
from app.services.database_service import RedisService
from app.services.config_service import ConfigService
from app.container import Get
from app.utils.helper import KeyBuilder
from app.utils.tools import Time
from app.models.security_model import ClientORM,ChallengeORM
from typing import Callable, Type,TypeVar
from tortoise.models import Model,ModelMeta

REDIS_CACHE_KEY = 3

T = TypeVar('T',bool,str,int,Model)

redisService:RedisService = Get(RedisService)
configService = Get(ConfigService)


def generate_cache_func(type_:Type[T],prefix='orm-cache',sep='-',expiry:int = 0):
    """
        Generates a set of cache-related functions (Cache, Get, Invalid) for storing, retrieving, 
        and invalidating objects in a Redis cache. The functions are tailored to work with a specific 
        object type and use a consistent key-building mechanism.
        Args:
            type_ (Type[T]): The type of the object to be cached. If the type is a ModelMeta, 
                             special handling is applied.
            prefix (str, optional): The prefix to use for cache keys. Defaults to 'orm-cache'.
            sep (str, optional): The separator to use in cache keys. Defaults to '-'.
            expiry (int, optional): The expiration time for cached objects in seconds. Defaults to 0 (no expiration).
        Returns:
            Tuple[Callable, Callable, Callable, Callable]: A tuple containing the following functions:
                - Cache: Stores an object in the cache.
                - Get: Retrieves an object from the cache.
                - Invalid: Invalidates (deletes) an object from the cache.
                - key_separator: A function to build cache keys.
    """
 
    key_builder,key_separator = KeyBuilder(prefix,sep)

    def kb(func:Callable):
        """
            Decorator for wrapping cache-related functions to ensure consistent key-building.
            Args:
                func (Callable): The function to wrap.
            Returns:
                Callable: The wrapped function with key-building logic applied.
        """
        @functools.wraps(func)
        async def wrapper(key,*args,**kwargs):
            key = key_builder(key)
            return await func(key,*args,**kwargs)
    
        return wrapper
    
    @kb
    async def Cache(key:str,obj:T):
        """
            Stores an object in the Redis cache.
            Args:
                key (str): The key under which the object will be stored.
                obj (T): The object to store in the cache.
            Returns:
                Any: The result of the Redis store operation.
        """
        if type(type_) == ModelMeta:
            obj = ...
        return await redisService.store(REDIS_CACHE_KEY,key,obj,expiry)
    
    @kb
    async def Get(key:str)->Type[T]|None:
        """
            Retrieves an object from the Redis cache.
            Args:
                key (str): The key of the object to retrieve.
            Returns:
                Type[T] | None: The retrieved object, or None if the key does not exist in the cache.
        """
        obj = await redisService.retrieve(REDIS_CACHE_KEY,key)   
        if type(type_) == ModelMeta:
            return type_(**obj) 
        return obj
    
    @kb
    async def Invalid(key:str):
        """
            Invalidates (deletes) an object from the Redis cache.
            Args:
                key (str): The key of the object to delete.
            Returns:
                Any: The result of the Redis delete operation.
        """
        return await redisService.delete(REDIS_CACHE_KEY,key)

    return Cache,Get,Invalid,key_separator
