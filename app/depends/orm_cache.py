import functools
from random import randint
import time
from uuid import UUID
from app.depends.funcs_dep import GetClient, GetLink, get_challenge,Get_Contact
from app.models.contacts_model import ContactORM, ContactSummary, ContentSubscriptionORM
from app.models.link_model import LinkORM
from app.services.admin_service import AdminService
from app.services.contacts_service import ContactsService
from app.services.database_service import RedisService
from app.services.config_service import ConfigService
from app.container import Get
from app.utils.helper import KeyBuilder
from app.utils.tools import Time
from app.models.security_model import ClientORM,ChallengeORM
from typing import Any, Callable, Type,TypeVar
from tortoise.models import Model,ModelMeta
from app.utils.helper import isprimitive_type
from app.utils.transformer import parse_time
import asyncio
from cachetools import LRUCache

REDIS_CACHE_KEY = 3

WILDCARD='*'

T = TypeVar('T',bool,str,int,Model)

redisService:RedisService = Get(RedisService)
configService:ConfigService = Get(ConfigService)
adminService:AdminService = Get(AdminService)
contactService:ContactsService = Get(ContactsService)


class CacheInterface:

    @staticmethod
    async def Get(key:str|list[str])->Type[T]|None:
        """
        Retrieves an object from the Redis cache.
        Args:
            key (str): The key of the object to retrieve.
        Returns:
            Type[T] | None: The retrieved object, or None if the key does not exist in the cache.
        """
        ...

    @staticmethod
    async def Invalid(key:str|list[str])->None:
        """
        Invalidates (deletes) an object from the Redis cache.
        Args:
            key (str): The key of the object to delete.
        Returns:
            Any: The result of the Redis delete operation.
        """
        ...

    @staticmethod
    async def Store(key:str|list[str],obj:T=None,exp:int=0,**kwargs):
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
    async def InvalidAll(mask:list[str]=None):
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
    def Key_Separator(key:str|list[str])->str:
        """
        Splits or processes a given key string based on a specific separator logic.

        Args:
            key (str): The input key string to be processed.

        Returns:
            str: The processed or modified key string.
        """
        ...

    @staticmethod
    def Cache(key:str|list[str],*args,expiry:int|None|Callable[[Any],int]=None,when_cond:Any=None,**kwargs)->T:
        """
        Caches the result of a database retrieval operation.
        This method attempts to retrieve an object from the cache using the provided key.
        If the object is not found in the cache, it retrieves the object from the database
        using the `db_get` callable, stores it in the cache with the specified expiry, and
        then returns the object.
        Args:
            key (str): The unique identifier for the cached object.
            expiry (int | None | Callable[[Any], int]): The expiration time for the cached object.
            - If an integer or float, it specifies the number of seconds before the cache expires.
            - If a callable, it is a function that takes the retrieved object as input and returns
              the expiration time in seconds.
            - If None or invalid, the default expiry time of 0 is used (immediate expiration).
            db_get (Callable): A callable (function or coroutine) used to retrieve the object from the database
            if it is not found in the cache.
            *args: Positional arguments to pass to the `db_get` callable.
            **kwargs: Keyword arguments to pass to the `db_get` callable.
        Returns:
            T | None: The cached or retrieved object. Returns `None` if the object could not be retrieved.
        Raises:
            TypeError: If `expiry` is not an integer, float, callable, or None.
        """
        ...

    @staticmethod
    def When(cond:Any)->bool:
        ...

def generate_cache_type(type_:Type[T],db_get:Callable[[Any],Any],index:int = 0,prefix:str|list[str]='orm-cache',sep:str|list[str]='/',expiry:int|str|Callable[[T],int|float] = 0,nx:bool=False, when:Callable[[Any],bool]|None=None,use_to_json:bool=True,max_size_memory_cache=1000)->Type[CacheInterface]:
    """
        Generates a cache interface class for managing cached objects with a consistent key-building mechanism.
            type_ (Type[T]): The type of the object to be cached. If it is a model, it should support initialization with keyword arguments.
            db_get (Callable[[Any], Any]): A callable function to retrieve data from the database. Can be synchronous or asynchronous.
            index (int, optional): Index to extract a specific element from the result if the result is a tuple or list. Defaults to 0.
            prefix (str | list[str], optional): Prefix for cache keys. Can be a string or a list of strings. Defaults to 'orm-cache'.
            sep (str | list[str], optional): Separator for building cache keys. Can be a string or a list of strings. Defaults to '/'.
            expiry (int | str, optional): Expiry time for cached objects. Can be an integer (seconds) or a string (e.g., '1h', '30m'). Defaults to 0 (no expiry).
            nx (bool, optional): If True, ensures that the cache key is only set if it does not already exist. Defaults to False.
            when (Callable[[Any], bool] | None, optional): A callable function to determine whether caching should occur based on a condition. Defaults to None.
            Type[CacheInterface]: A dynamically generated cache interface class with methods for storing, retrieving, and invalidating cached objects.

        The generated cache interface includes the following methods:
            - Store: Stores an object in the cache with an optional expiry time.
            - Get: Retrieves an object from the cache by its key.
            - Invalid: Invalidates a specific cache key.
            - InvalidAll: Invalidates all cache keys with a specific prefix or mask.
            - Cache: Retrieves an object from the cache or database, storing it in the cache if it is not already cached.
            - Key_Separator: Builds a cache key using the specified separator.
            - When: Evaluates the provided condition to determine whether caching should occur.
    """
    IN_MEMORY_CACHE = LRUCache(max_size_memory_cache)
 
    key_builder,key_separator = KeyBuilder(prefix,sep)

    async def DB_Get(*args, **kwargs):
        result = await db_get(*args, **kwargs) if asyncio.iscoroutinefunction(db_get) else db_get(*args, **kwargs)
        if isinstance(result, (tuple, list)) and 0 <= index < len(result):
            return result[index]
        return result

    def Set_Expiry(_expiry):
        if isinstance(_expiry,(int,float)):
            if _expiry <= 0:
                _expiry = 0
        elif isinstance(_expiry,str):
            try:
                _expiry = parse_time(_expiry)
            except:
                _expiry=0
        else:
            _expiry = 0
        return _expiry

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
                if not isinstance(key,(str,tuple,list)):
                    key = str(key)
                
                if isinstance(key,(tuple,list)):
                    key = [str(k)for k in key]                

                key = key_builder(key)
                return await func(key,*args,**kwargs)
        
            return wrapper
        
        @kb
        @staticmethod
        async def Store(key:str|list[str],obj:T=None,exp=expiry,**kwargs):

            exp = Set_Expiry(exp)
            if obj == None:
                obj = await DB_Get(**kwargs)

            if type(type_) == ModelMeta:
                obj:Model = obj
                temp = {}
                if hasattr(obj,'to_json') and use_to_json:
                    temp = obj.to_json
                else:
                    for field in obj._meta.fields_map:
                        attr = getattr(obj, field)
                        if isinstance(attr,UUID):
                            attr = str(attr)
                        if isprimitive_type(attr):
                            temp[field] =attr
            
            return await redisService.store(REDIS_CACHE_KEY,key,temp,exp,nx)
        
        @kb
        @staticmethod
        async def Get(key:str|list[str])->Type[T]|None:
            
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
        async def Invalid(key:str|list[str]):
            return await redisService.delete(REDIS_CACHE_KEY,key)
        
        @staticmethod
        async def InvalidAll(mask:list[str]=None):

            if isinstance(prefix,str):
                p=prefix
                is_s_p = True
            else:
                if mask == None:
                    raise ValueError('Value cant be none')
                
                is_s_p = False
                p=key_builder(mask)

            return await redisService.delete_all(REDIS_CACHE_KEY,p,is_s_p)

        @staticmethod
        async def Cache(key,*args,expiry:int|None|Callable[[Any],int]=expiry,when_cond:Any=None,**kwargs):
            
            if not ORMCache.When(when_cond):
                return await DB_Get(*args,**kwargs)

            obj:T|None =  await ORMCache.Get(key)
            if obj == None:
                obj = await DB_Get(*args,**kwargs)
                
                if obj == None:
                    return None
                    
                if callable(expiry):
                    expiry = expiry(obj)
                    if expiry <= 0:
                        return 
                    else:
                        expiry + randint(1,5)
                await ORMCache.Store(key,obj,expiry)
            
            return obj

        @staticmethod
        def Key_Separator(key:str|list[str]):
            return key_separator(key)
        
        @staticmethod
        def When(args):
            if when == None:
                return True
            if not callable(when):
                #raise NotImplementedError
                return True

            return when(args)

        @kb
        @staticmethod
        async def Exists(key:str|list[str]):
            return await redisService.exists(REDIS_CACHE_KEY,key)

    return ORMCache

ClientORMCache = generate_cache_type(ClientORM,GetClient(True,True),prefix=['orm-group','client'])
BlacklistORMCache = generate_cache_type(bool,adminService.is_blacklisted,prefix=['orm-blacklist','client'],expiry=lambda o:o[1])
ChallengeORMCache = generate_cache_type(ChallengeORM,get_challenge,prefix='orm-challenge',expiry=lambda o:o.expired_at_auth.timestamp()-time.time())
LinkORMCache = generate_cache_type(LinkORM,GetLink(True,False),prefix='orm-link')
ContactORMCache = generate_cache_type(ContactORM,Get_Contact(True,True,),prefix='orm-contact',use_to_json=True)
ContactSummaryORMCache = generate_cache_type(ContactSummary,contactService.read_contact,prefix='orm-contact-summary',use_to_json=False)
#ContentSubORMCache = generate_cache_type(ContentSubscriptionORM,)
