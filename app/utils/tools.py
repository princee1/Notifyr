from functools import wraps
from time import perf_counter
from typing import Callable


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