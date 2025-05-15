import asyncio
from typing import Annotated, Any, Literal, Dict,TypedDict
from fastapi import BackgroundTasks, Depends, Query, Request, Response
from app.classes.broker import MessageBroker, SubjectType,exception_to_json
from app.classes.celery import SchedulerModel
from app.depends.dependencies import get_request_id
from app.models.email_model import CustomEmailModel, EmailTemplateModel
from app.models.link_model import LinkORM
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.container import Get
from .variables import *
from app.services.link_service import LinkService
from app.services.logger_service import LoggerService
from app.services.reactive_service import ReactiveService, ReactiveType,Disposable
from app.errors.async_error import ReactiveSubjectNotFoundError
from time import perf_counter,time
from app.classes.stream_data_parser import StreamContinuousDataParser, StreamDataParser, StreamSequentialDataParser
from app.utils.helper import uuid_v1_mc,UUID
from email.utils import make_msgid as msid
from datetime import datetime, timedelta, timezone

def  make_msgid():
    configService:ConfigService = Get(ConfigService)
    return msid()

class EmailTracker:

    def __init__(self,scheduler:SchedulerModel, email_id:Annotated[UUID,Depends(uuid_v1_mc)],message_id:Annotated[str,Depends(make_msgid)],track_email:bool=Depends(track_email)):
        self.email_id = str(email_id)
        self.message_id = message_id
        self.will_track = track_email
        
        self.configService = Get(ConfigService)

        content:EmailTemplateModel|CustomEmailModel = scheduler.content
        self.emailMetaData=content.meta

        if self.will_track:
            self.emailMetaData.Disposition_Notification_To = self.configService.SMTP_EMAIL
            self.emailMetaData.Return_Receipt_To = self.configService.SMTP_EMAIL
            
            self.emailMetaData.X_Email_ID = self.email_id

        self.emailMetaData.Message_ID = self.message_id
        
    def track_event_data(self,spam:tuple[float,str]=(100,'no-spam'))->dict:
        spam_confidence,spam_label = spam
        # Convert datetime fields to timezone-aware ISO 8601 string representation
        now = datetime.now(timezone.utc).isoformat()
        expired_tracking_date = (now + timedelta(days=30)).isoformat()

        # Create the EmailTrackingORM object
        return {
            "recipient": self.emailMetaData.To,
            "email_id": self.email_id,
            "message_id": self.message_id,
            "spam_confidence": spam_confidence,
            "spam_label": spam_label,
            "date_sent": now,
            "last_update": now,
            "expired_tracking_date": expired_tracking_date,
        }



class SubjectParams:

    def __init__(self,request:Request,sid_type:Annotated[str|None,Depends(sid_type_params)],subject_id:Annotated[str|None,Depends(subject_id_params)]):
        self.sid_type = sid_type
        self.subject_id = subject_id,
        if isinstance(self.subject_id,tuple):
            self.subject_id = list(self.subject_id)[0]

class LinkArgs:

    class ServerScopedParams(TypedDict):
        client_id:str | None = None
        group_id:str|None = None
        contact_id:str|None = None
        session_id:str|None = None
        message_id:str|None = None
        link_id:str|None = None
        subject_id:str|None = None

    class IdsTypeParams(TypedDict):
        cid:str |None = None
        gid:str |None = None
        lid:str |None = None
        ctid:str |None = None

        cid_type :Literal['client','contact']
        sid_type: SubjectType

    server_scoped_params = ["client_id", "group_id", "contact_id", "session_id","message_id","link_id","subject_id"]
    ids_type = ["cid","gid","lid","ctid","sid_type"]
    
    def __init__(self, request: Request):
        self.request = request
        self._filter_params()
        self.configService:ConfigService = Get(ConfigService)
        self.linkService:LinkService = Get(LinkService)
    
    def __getitem__(self,params)->str|None:
        return self.request.query_params.get(params,None)

    def _filter_params(self) -> dict:
        scoped_params ={}
        ids_type_params = {}
        self._link_params = {}

        for key,value in self.request.query_params.items():

            if key in self.ids_type:
                ids_type_params[key] = value

            elif key in self.server_scoped_params:
                scoped_params[key]=value
            else:
                self._link_params[key] =value

        self.server_scoped = self.ServerScopedParams(**scoped_params) 
        self.ids_type_params = self.IdsTypeParams(**ids_type_params)

    @property
    def all_params(self):
        return self.request._query_params.__str__()

    @property
    def raw_link_params(self):
        return "&".join([ f'{key}={value}' for key,value in self._link_params.items()])
    
    def raw_filtered_out_params(self,attr,include=()):
        return "&".join([ f'{key}={value}' for key,value in getattr(self,attr).items() if key in include])
    
    def create_link(self,link:LinkORM,path:str,include_scoped_out=(),include_ids_type=()):
        if link == None:
            url = self.request.url.hostname
        else:
            url = link.link_url
            
        if not url.endswith("/"):
            url+="/"
        
        url+=path if path else ""
        url+="?"
        url+=self.raw_link_params
        url+=self.raw_filtered_out_params('server_scoped',include_scoped_out)
        url+=self.raw_filtered_out_params('ids_type_params',include_ids_type)
        return url
    
    @property
    def subject_id(self):
        sid_type = self.ids_type_params.get('sid_type','plain')
        match sid_type:
            case 'contact':
                return sid_type,self.server_scoped.get("contact_id",None)
            case 'message':
                return sid_type,self.server_scoped.get('message_id',None)
            case 'plain':
                return sid_type,self.server_scoped.get("subject_id",None)
            case 'session':
                return sid_type,self.server_scoped.get("session_id",None)
            case _:
                return sid_type,self.server_scoped.get('subject_id',None)
            
class Broker:
    
    def __init__(self,request:Request,response:Response,backgroundTasks:BackgroundTasks):
        self.reactiveService:ReactiveService = Get(ReactiveService)
        self.redisService:RedisService = Get(RedisService)
        self.configService:ConfigService = Get(ConfigService)
        
        self.backgroundTasks = backgroundTasks
        self.request = request
        self.response = response

    def publish(self,channel:str,sid_type:SubjectType,subject_id:str, value:Any,state:Literal['next','complete']='next'):

        if self.configService.pool:
            subject = self.reactiveService[subject_id]
            if isinstance(value,Exception):
                self.backgroundTasks.add_task(subject.on_error,value) 
            else:
                self.backgroundTasks.add_task(subject.on_next,value)
        
        else:
            if subject_id == None:
                return 
            if isinstance(value,Exception):
                error = exception_to_json(value)
                message_broker = MessageBroker(error=error,sid_type=sid_type,subject_id=subject_id,state='error',value=None)
            else:
                message_broker = MessageBroker(error=None,sid_type=sid_type,subject_id=subject_id,state=state,value=value)

            self.backgroundTasks.add_task(self.redisService.publish_data,channel,message_broker)

    def stream(self,channel,value,handler=None,args=None,kwargs=None):
        
        async def callback():
            if asyncio.iscoroutinefunction(handler):
                await handler(*args,**kwargs)
            else:
                handler(*args,kwargs) 

        self.backgroundTasks.add_task(self.redisService.stream_data,channel,value)
        
class KeepAliveQuery:

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
        return f'KeepAliveQuery(timeout={self.timeout}, subject_id={subj_id}, request_id={self.x_request_id})'
