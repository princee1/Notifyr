import functools
from uuid import UUID
from app.models.link_model import LinkORM
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

class CacheInterface:

    @staticmethod
    async def Get(key:str)->Type[T]|None:
        """
        Retrieves an object from the Redis cache.
        Args:
            key (str): The key of the object to retrieve.
        Returns:
            Type[T] | None: The retrieved object, or None if the key does not exist in the cache.
        """
        ...

    @staticmethod
    async def Invalid(key:str)->None:
        """
        Invalidates (deletes) an object from the Redis cache.
        Args:
            key (str): The key of the object to delete.
        Returns:
            Any: The result of the Redis delete operation.
        """
        ...

    @staticmethod
    async def Cache(key:str,obj:T,exp:int=0):
        """
        Stores an object in the Redis cache.
        Args:
            key (str): The key under which the object will be stored.
            obj (T): The object to store in the cache.
        Returns:
            Any: The result of the Redis store operation.
        """
        ...

    @staticmethod
    async def InvalidAll():
        """
            Invalidates all cached ORM data.

            This method is a static asynchronous function that clears or invalidates
            all cached data related to the ORM (Object-Relational Mapping). It is 
            typically used to ensure that stale or outdated data is removed from the 
            cache, forcing the system to fetch fresh data from the database.

            Note:
            The implementation details of this method are not provided in the 
            current context. Ensure that the actual implementation handles 
            concurrency and error scenarios appropriately.
            """
        ...

    @staticmethod
    def Key_Separator(key:str)->str:
        """
        Splits or processes a given key string based on a specific separator logic.

        Args:
            key (str): The input key string to be processed.

        Returns:
            str: The processed or modified key string.
        """
        ...


def generate_cache_type(type_:Type[T],prefix='orm-cache',sep='-',expiry:int = 0)->Type[CacheInterface]:
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

    class ORMCache(CacheInterface):

        @staticmethod
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
                if type(key) != str:
                    key = str(key)

                key = key_builder(key)
                return await func(key,*args,**kwargs)
        
            return wrapper
        
        @kb
        @staticmethod
        async def Cache(key:str,obj:T,exp=expiry):
            
            if type(type_) == ModelMeta:
                obj:Model = obj
                temp = {}
                for field in obj._meta.fields_map:
                    attr = getattr(obj, field)
                    if isinstance(attr,UUID):
                        attr = str(attr)
                    temp[field] =attr
            return await redisService.store(REDIS_CACHE_KEY,key,temp,exp)
        
        @kb
        @staticmethod
        async def Get(key:str)->Type[T]|None:
            
            obj = await redisService.retrieve(REDIS_CACHE_KEY,key)   
            if obj == None:
                print(f'Cache MISS key: {key} | prefix: {prefix}')
                return None

            print(f'Cache HIT key: {key} | prefix: {prefix}')
            if type(type_) == ModelMeta:
                return type_(**obj) 
            return obj
        
        @kb
        @staticmethod
        async def Invalid(key:str):
            return await redisService.delete(REDIS_CACHE_KEY,key)
        
        @staticmethod
        async def InvalidAll():
            return await redisService.delete_all(REDIS_CACHE_KEY,prefix)

        @staticmethod
        def Key_Separator(key:str):
            return key_separator(key)
    
    return ORMCache

ClientORMCache = generate_cache_type(ClientORM,'client')
BlacklistORMCache = generate_cache_type(bool,'blacklist')
ChallengeORMCache = generate_cache_type(ChallengeORM,'challenge')
LinkORMCache = generate_cache_type(LinkORM,'link')
