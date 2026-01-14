import functools
from typing import Any, Literal
from fastapi import BackgroundTasks
from app.container import Get
from app.definition._cost import Cost, DataCost
from app.definition._service import BaseMiniServiceManager, MiniStateProtocol, ServiceDoesNotExistError, ServiceStatus, StateProtocol,_CLASS_DEPENDENCY, StateProtocolMalFormattedError
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.cost_service import CostService
from app.services.database.redis_service import RedisService
from app.services.reactive_service import ReactiveService
from app.utils.constant import SubConstant
from app.utils.helper import issubclass_of
from app.utils.tools import Mock
from app.classes.broker import MessageBroker, SubjectType,exception_to_json
from app.depends.variables import *
import asyncio

class Broker:
    
    def __init__(self,request:Request,response:Response,backgroundTasks:BackgroundTasks):
        self.reactiveService:ReactiveService = Get(ReactiveService)
        self.redisService:RedisService = Get(RedisService)
        self.configService:ConfigService = Get(ConfigService)
        self.costService:CostService = Get(CostService)
        self.uvicornWorkerService:UvicornWorkerService = Get(UvicornWorkerService)
        
        self.backgroundTasks = backgroundTasks
        self.request = request
        self.response = response

    @Mock()
    def publish(self,channel:str,sid_type:SubjectType,subject_id:str, value:Any,state:Literal['next','complete']='next'):

        if self.uvicornWorkerService.pool:
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

    @Mock()
    def stream(self,channel,value,handler=None,args=None,kwargs=None):
        
        async def callback():
            if asyncio.iscoroutinefunction(handler):
                await handler(*args,**kwargs)
            else:
                handler(*args,kwargs) 

        self.backgroundTasks.add_task(self.redisService.stream_data,channel,value)
    
    @Mock()
    def push(self,db:int,name,*values):
        self.backgroundTasks.add_task(self.redisService.push,db,name,*values)

    #@Mock()
    def add(self,function,*args,**kwargs):
        self.backgroundTasks.add_task(function,*args,**kwargs)

    def propagate(self,protocol:StateProtocol|MiniStateProtocol):

        if isinstance(protocol.get('service',None),type):
            protocol['service'] = protocol['service'].__name__

        if protocol['service'] not in _CLASS_DEPENDENCY.keys():
            raise ServiceDoesNotExistError
        
        if protocol.get('id',None) != None:
            sub_queue = SubConstant.MINI_SERVICE_STATUS
            if not issubclass_of(BaseMiniServiceManager,_CLASS_DEPENDENCY[protocol['service']]):
                raise StateProtocolMalFormattedError('Service is not a MiniServiceManager')
        else:
            sub_queue = SubConstant.SERVICE_STATUS

        try:
            if protocol.get('status',None) is not None:
                ServiceStatus(protocol['status'])
        except:
            raise StateProtocolMalFormattedError

        self.backgroundTasks.add_task(self.redisService.publish_data,sub_queue,protocol)
    
    def wait(self,seconds:float):

        self.backgroundTasks.add_task(asyncio.sleep,seconds)
  