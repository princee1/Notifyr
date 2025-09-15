from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from app.classes.broker import SubjectType
from app.definition._error import BaseError
from app.definition._service import BaseService, Service
from app.errors.async_error import LockNotFoundError, ReactiveSubjectNotFoundError
from app.interface.timers import IntervalInterface, SchedulerInterface
from app.services.config_service import ConfigService
from app.services.logger_service import LoggerService
from app.utils.helper import generateId
import asyncio
from reactivex import Subject
from reactivex.disposable import Disposable


ReactiveType= Literal['HTTP','Celery','BackgroundTask','RedisPubSub','RedisStream','RedisQueue']


@dataclass
class ReactiveSubject():
    name:str
    reactive_type:ReactiveType
    subject_id:str
    sid_type:SubjectType
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
    
    def lock_lock(self,x_request_id):
        lock = self.lock.get(x_request_id,None)
        if lock is None:
            raise LockNotFoundError(f"Lock not found for x_request_id: {x_request_id}")
        lock._locked = True

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

@Service
class ReactiveService(BaseService,SchedulerInterface):
    
    def __init__(self,configService:ConfigService,loggerService:LoggerService):
        BaseService.__init__(self)
        SchedulerInterface.__init__(self,None) # Fire reactive even if the process ends
        self.configService = configService
        self.loggerService = loggerService
        self._subscriptions:dict[str,ReactiveSubject] = {}
        

    def create_subject(self,name:str,type_:ReactiveType,subject_id=None,sid_type:SubjectType='plain') -> ReactiveSubject:
        if sid_type == 'plain':
            subject_id = generateId(20)
        else:
            if subject_id == None:
                raise ...
        
        rxSub= ReactiveSubject(name=name,reactive_type=type_,subject_id=subject_id,sid_type=sid_type)
        self._subscriptions[rxSub.subject_id]=rxSub
        return rxSub
    
    def delete_subject(self,subject_id:str):
        rx_subject = self[subject_id]
        rx_subject.on_completed()
        del self._subscriptions[subject_id]

        
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

    def __getitem__(self,subject_id):
        subject:ReactiveSubject  | None = self._subscriptions.get(subject_id,None)
        if subject == None:
            raise ReactiveSubjectNotFoundError(subject_id)
        return subject

    def publish(self):
        ...
    
    def build(self,build_state=-1):
        ...
    

    
    