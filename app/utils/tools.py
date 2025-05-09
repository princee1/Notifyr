from functools import wraps
from time import perf_counter
from typing import Callable
from cachetools import LRUCache


def hash_args(args):
    a, k = args
    return str(a)+"<==>"+str(k)

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
        start_time = perf_counter()
        result = func(*args, **kwargs)
        end_time = perf_counter()
        print(f'Function Object: {str(func)}\nTime: {end_time-start_time} sec')
        return result

    return wrapper

def Cache(maxsize:float=100):
    
    cache = LRUCache(maxsize)

    def callback(func:Callable):
    
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = hash_args((args, kwargs))
            if key in cache:
                print(f"Cache hit for key: {key}")
                return cache[key]
            print(f"Cache miss for key: {key}")
            result = await func(*args, **kwargs)
            cache[key] = result
            return result
        

        return wrapper
    return callback
        