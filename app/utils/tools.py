from functools import wraps
import json
from time import perf_counter,time,time_ns, sleep  as time_sleep
from typing import Callable, Literal, get_args
from aiohttp_retry import Any
from cachetools import LRUCache
import asyncio
from fastapi_cache.coder import JsonCoder,object_hook
from fastapi_cache.decorator import cache


class MyJSONCoder(JsonCoder):
    
    @classmethod
    def decode(cls, value: bytes|str) -> Any:
        """Decode bytes to JSON object."""
        if isinstance(value, str):
            return json.loads(value, object_hook=object_hook)
        try:
            return super().decode(value)
        except Exception as e:
            print(f"Decoding error: {e}")
            return None

def Time(func: Callable):
    """
    A decorator that measures the execution time of a function.

    Args:
        func (Callable): The function to be decorated and timed.

    Returns:
        Callable: A wrapper function that calls the original function and prints its execution time.

    The decorator prints the time taken by the function to execute, along with the function's name
    and a hash of the arguments passed to it.

    Example:
    >>> \n\t@Time
        def example_function(x, y):
            # Some time-consuming computations
            return x + y
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time()
        result = func(*args, **kwargs)
        end_time = time()
        print(f'Function Object: {str(func)}\nTime: {end_time-start_time} sec')
        return result


    @wraps(func)
    async def wrapper_async (*args, **kwargs):
        start_time = time()
        result = await func(*args, **kwargs)
        end_time = time()
        print(f'Function Object: {str(func)}\nTime: {end_time-start_time} sec')
        return result
    return wrapper_async if asyncio.iscoroutinefunction(func) else wrapper

def Cache(cache_type:Literal['custom-in-memory','fastapi-default-cache'] = 'custom-in-memory'):
    def hash_args(args):
        a, k = args
        return str(a)+"<==>"+str(k)

    
    def CustomInMemoryCache(maxsize: int = 1000):
        """
        A decorator to cache function results in memory using LRUCache.
        Args:
            maxsize (int): Maximum size of the cache. Defaults to 1000.
        Returns:
            Callable: A decorator that caches the function's return value.
        """
        


        if not isinstance(maxsize, int) or maxsize <= 0:
            raise ValueError("maxsize must be a positive integer")

        cache = LRUCache(maxsize)

        def callback(func:Callable):
        
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = hash_args((args, kwargs))
                if key in cache:
                    print(f"Cache hit for key: {key}")
                    return cache[key]
                print(f"Cache miss for key: {key}")
                result = await func(*args, **kwargs)
                cache[key] = result
                return result

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = hash_args((args, kwargs))
                if key in cache:
                    print(f"Cache hit for key: {key}")
                    return cache[key]
                print(f"Cache miss for key: {key}")
                result = func(*args, **kwargs)
                cache[key] = result
                return result
            

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return callback

    @wraps(cache)
    def DefaultCache(*args, **kwargs):
        """
        A decorator to cache function results using Redis.
        Args:
            **kwargs: Additional keyword arguments for the cache configuration.
        Returns:
            Callable: A decorator that caches the function's return value.
        """
        def callback(func:Callable):
            return cache(*args, **kwargs)(func)

        return callback

    if cache_type == 'in-memory':
        return CustomInMemoryCache
    elif cache_type == 'fastapi-default-cache':
        return DefaultCache
    else:
        raise ValueError("Invalid cache type. Choose 'in-memory' or 'fastapi-default-cache'.")

def Mock(sleep:float=2,result:Any = None,same:bool=False):
    """
    A decorator to mock asynchronous function execution by introducing a delay.
    This decorator wraps an asynchronous function and replaces its execution
    with a delay using `asyncio.sleep`. It is useful for testing or simulating
    asynchronous behavior without executing the actual function logic.
    Args:
        sleep (float): The duration (in seconds) to delay the execution. Defaults to 2 seconds.
    Returns:
        Callable: A decorator that replaces the wrapped function's execution with a delay.
    """

    def build_result(r:Any)->Any:
        if callable(r):
            return r()

        if isinstance(r, Exception) or issubclass(type(r), BaseException):
            raise r
        
        if isinstance(r, dict):
            return {k: build_result(v) for k, v in r.items()}

        if isinstance(r,list):
            return [build_result(item) for item in r]

        return r

    if same:
        result= build_result(result)   

    def wrapper(func:Callable):

        @wraps(func)
        async def callback_async(*args,**kwargs):
            await asyncio.sleep(sleep)
            return build_result(result) if not same else result

        @wraps(func)
        def callback_sync(*args,**kwargs):
            
            return build_result(result) if not same else result

        return callback_async if asyncio.iscoroutinefunction(func) else callback_sync    

    return wrapper

def RunAsync(func:Callable):
    """
    The `RunAsync` function takes a callable function and returns an asynchronous wrapper function that
    runs the original function in a separate thread if it's not already a coroutine function.
    
    :param func: The `func` parameter in the `RunAsync` function is expected to be a callable object,
    such as a function or a method, that may or may not be a coroutine function
    :type func: Callable
    :return: The `RunAsync` function returns a coroutine function.
    """

    if asyncio.iscoroutinefunction(func):
        return func  # type: ignore

    @wraps(func)
    async def wrapper(*args,**kwargs):
        return await asyncio.to_thread(func,*args,**kwargs)
    
    return wrapper