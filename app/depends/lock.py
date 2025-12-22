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
        async with tortoiseConnection.statusLock.reader:
            if tortoiseConnection.service_status not in _valid_state:
                return []
            return await func(entries)
    
    return callback

def LockLogicDecorator(callbacks:dict[str,Callable]):
    for k,v in callbacks.items():
        callbacks[k] = lock_logic(v)