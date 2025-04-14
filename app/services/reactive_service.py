from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from app.definition._error import BaseError
from app.definition._service import Service, ServiceClass
from app.errors.async_error import LockNotFoundError, ReactiveSubjectNotFoundError
from app.interface.timers import IntervalInterface
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.logger_service import LoggerService
from app.utils.helper import generateId
import asyncio
from reactivex import Subject


ReactiveType= Literal['HTTP','Celery','BackgroundTask','RedisPubSub','RedisStream','RedisQueue']


@dataclass
class ReactiveSubject():
    name:str
    type_:ReactiveType
    id_:str = field(default_factory=lambda:generateId(60))
    lock:dict[str,asyncio.Lock] = field(default_factory=dict) 
    subject:Subject = field(default_factory=Subject)


    async def wait_for(self,x_request_id,timeout:float=None,default_result:Any={}) -> Any:
        if timeout is None or timeout < 0:
            return
        else:
            try:
                lock = self.lock.get(x_request_id,None)
                if lock is None:
                    raise LockNotFoundError(f"Lock not found for x_request_id: {x_request_id}")
                return await asyncio.wait_for(lock.acquire(),timeout=timeout)
            except asyncio.TimeoutError as e:
                raise asyncio.TimeoutError(default_result)
            except TimeoutError as e:
                raise asyncio.TimeoutError(default_result)
    
    def register_lock(self,x_request_id) -> asyncio.Lock:
        lock = asyncio.Lock()
        lock._locked = True
        self.lock[x_request_id]=lock
        return lock      

    def dispose_lock(self,x_request_id):
        try:
            del self.lock[x_request_id]
        except KeyError:
            pass
        
    def on_next(self,v:Any):
        self.subject.on_next(v)
        for lock in self.lock.values():
            if lock.locked():
                lock.release()
        
    def on_error(self,e:Exception):
        self.subject.on_error(e)
        for lock in self.lock.values():
            if lock.locked():
                lock.release()

    def on_completed(self):
        self.subject.on_completed()
        for lock in self.lock.values():
            if lock.locked():
                lock.release()

@ServiceClass
class ReactiveService(Service,IntervalInterface):
    
    def __init__(self,configService:ConfigService,redisService:RedisService,loggerService:LoggerService):
        Service.__init__(self)
        IntervalInterface.__init__(self,start_now=True, interval=0.10)
        self.configService = configService
        self.redisService = redisService
        self.loggerService = loggerService
        self._subscriptions:dict[str,ReactiveSubject] = {}
        

    def create_subject(self,name:str,type_:ReactiveType) -> ReactiveSubject:
        rxSub= ReactiveSubject(name=name,type_=type_)
        self._subscriptions[rxSub.id_]=rxSub
        return rxSub
        
    def subscribe(self,rxId:str,on_next:Callable[[Any],None],on_error:Callable=None,on_completed:Callable=None):
        rxSub= self._subscriptions.get(rxId,None)
        if rxSub is None:
            raise ReactiveSubjectNotFoundError(f"Reactive object with id {rxId} not found.")
        disposable = rxSub.subject.subscribe(
            on_next=on_next,
            on_error=on_error,
            on_completed=on_completed
        )
        return disposable

    def publish(self):
        ...
    
    def build(self):
        ...
    

    
    