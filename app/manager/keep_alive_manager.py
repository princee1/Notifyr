from time import perf_counter,time
from typing import Annotated, Any
from fastapi import Depends
from app.container import Get
from app.services.logger_service import LoggerService
from app.services.reactive_service import ReactiveService, ReactiveType,Disposable
from app.errors.async_error import ReactiveSubjectNotFoundError
from app.depends.dependencies import get_request_id
from app.classes.stream_data_parser import StreamContinuousDataParser, StreamSequentialDataParser
from app.depends.variables import *

keep_connection:Callable[[Request],bool]=get_query_params('keep_connection','false',True)


class KeepAliveManager:

    def __init__(self, response: Response, x_request_id: Annotated[str, Depends(get_request_id)], keep_alive: Annotated[bool, Depends(keep_connection)], timeout: int = Query(0, description="Time in seconds to delay the response", ge=0, le=60*3)):
        self.timeout = timeout
        self.response = response
        self.x_request_id = x_request_id
        self.keep_alive = keep_alive

        self.value = {}
        self.error = None
        self.subscription:dict[str,Disposable] = {}


        self.start_time = perf_counter()
        self.rx_subject = None

        self.reactiveService: ReactiveService = Get(ReactiveService)
        self.loggerService: LoggerService = Get(LoggerService)

        self.subject_list:list[str] = []
        self.parser:StreamContinuousDataParser|StreamSequentialDataParser= None

    def set_stream_parser(self,parser):
        self.parser = parser

    def register_subject(self,subject_id:str,only_subject:bool):
        subscription = self.reactiveService.subscribe(
            subject_id,
            on_next= self.on_next,
            on_completed=self.on_complete,
            on_error=self.on_error
        )
        
        if only_subject:
            self.rx_subject = self.reactiveService[subject_id]
        else:
            self.subject_list.append(subject_id)
        
        self.subscription[subject_id] = subscription

    def create_subject(self, reactiveType: ReactiveType):

        if self.keep_alive:
            rx_subject = self.reactiveService.create_subject(self.x_request_id, reactiveType)
            rx_id = rx_subject.subject_id

            subscription = self.reactiveService.subscribe(
                rx_id,
                on_next=self.on_next,
                on_error=self.on_error,
                on_completed=self.on_complete
            )
            self.rx_subject = rx_subject
            self.subscription[rx_id] =subscription
            return rx_subject.subject_id
        else:
            return None

    def on_next(self, v: dict):
        try:
            state = v['state']
            if state in self.parser.state:
                value = {state:v['data']}
                self.value.update(value)

            self.parser.up_state(state)

            self.on_error(None)
        except Exception as e:
            self.on_error(e)

    def on_error(self, e: Exception):
        self.process_time = perf_counter() - self.start_time
        self.error = e
        if self.error !=None:
            setattr(self.error, 'process_time', self.process_time)

    def on_complete(self,):
        self.parser._completed = True

    def register_lock(self,subject_id=None):
        if subject_id == None:
            self.rx_subject.register_lock(self.x_request_id)
        else:
            rx_sub = self.reactiveService._subscriptions.get(subject_id,None)
            if rx_sub != None:
                rx_sub.register_lock(self.x_request_id)
            else:
                raise ReactiveSubjectNotFoundError(subject_id)

    def dispose(self):

        self.process_time = perf_counter() - self.start_time
        
        for rx_sub_id in self.subject_list:
            rx_sub = self.reactiveService._subscriptions.get(rx_sub_id,None)
            if rx_sub==None:
                continue
            rx_sub.dispose_lock(self.x_request_id)
            if rx_sub_id in self.subscription:
                self.subscription[rx_sub_id].dispose()

        if self.rx_subject !=None:
            self.subscription[self.rx_subject.subject_id].dispose()
            self.reactiveService.delete_subject(self.rx_subject.subject_id)
            
    async def wait_for(self, result_to_return: Any = None, coerce: str = None,subject_id=None):
        if self.keep_alive:
            if subject_id == None:
                rx_sub = self.rx_subject
            else:
                rx_sub = self.reactiveService._subscriptions.get(subject_id,None)
                if rx_sub != None:
                    rx_sub.register_lock(self.x_request_id)
                else:
                    raise ReactiveSubjectNotFoundError(subject_id)
            current_timeout = self.timeout
            current_time = time()

            while True:
                await rx_sub.wait_for(self.x_request_id,current_timeout, result_to_return)
                if self.error != None:
                    raise self.error
                
                if self.parser.completed:
                    break
                rx_sub.lock_lock(self.x_request_id)

                delta = self._compute_delta(current_timeout, current_time)
                current_time= time()
                current_timeout -=delta 

            key = 'value' if coerce == None else coerce
            return {
                key: self.value,
                'results': result_to_return,
            }
        else:
            return result_to_return

    def _compute_delta(self, current_timeout, current_time):
        delta= time() - current_time

        if delta> current_timeout:
            raise TimeoutError
        return delta

    def __repr__(self):
        subj_id = None if self.rx_subject == None else self.rx_subject.subject_id
        return f'KeepAliveManager(timeout={self.timeout}, subject_id={subj_id}, request_id={self.x_request_id})'
