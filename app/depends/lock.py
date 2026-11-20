import asyncio
import functools
from typing import Callable
from app.container import Get
from app.definition._service import ServiceStatus
from app.services.database.tortoise_service import TortoiseConnectionService

_valid_state = {ServiceStatus.AVAILABLE,ServiceStatus.PARTIALLY_AVAILABLE,ServiceStatus.WORKS_ALMOST_ATT}

def lock_logic(func:Callable[[list[tuple[str,dict]]],set]):

    @functools.wraps(func)
    async def callback(entries):
        tortoiseConnection:TortoiseConnectionService = Get(TortoiseConnectionService)
        async with tortoiseConnection.lock('reader'):
            if tortoiseConnection.service_status not in _valid_state:
                return []
            return await func(entries)
    
    return callback

def LockLogicDecorator(callbacks:dict[str,Callable]):
    for k,v in callbacks.items():
        callbacks[k] = lock_logic(v)


def inject_set(func:Callable):
    @functools.wraps(func)
    async def wrapper(*args,**kwargs):
        valid_entries = set()
        invalid_entries = set()
        kwargs['valid_entries'] = valid_entries
        kwargs['invalid_entries'] = invalid_entries

        return await wrapper(*args,**kwargs)

    return wrapper


def retry_logic(retry:int,sleep_time:int,*error):
    def wrapper(func:Callable):
        async def callback(*args,**kwargs):
            retry_count = 0
            while retry_count < retry:
                try:
                    return await func(*args,**kwargs)
                    break  # Exit the loop if successful
                except (*error,) as e:
                    retry_count += 1
                    if retry_count == retry:
                        raise e
                    else:
                        await asyncio.sleep(sleep_time)
                except Exception as e:
                    raise e
        return callback
    
    return wrapper