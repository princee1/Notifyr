from typing import Annotated
from fastapi import Depends, Request, Response,status
from app.container import Get, InjectInMethod
from app.decorators.handlers import APSSchedulerHandler, AsyncIOHandler, CeleryTaskHandler, ServiceAvailabilityHandler, WebSocketHandler
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.services.celery_service import CeleryService
from app.services.task_service import TaskService
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.security_service import JWTAuthService
from app.depends.dependencies import get_auth_permission
from app.classes.auth_permission import AuthPermission, MustHave, Role
from apscheduler.job import Job


REDIS_EXPIRATION = 360000
RESULT_PREFIX = 'result'

CELERY_PREFIX= 'celery'
BACKGROUND_PREFIX  = 'background'
APS_SCHEDULER='aps'

@UseRoles([Role.RESULT])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@PingService([CeleryService],__celery_availability__=True)
@HTTPRessource(prefix=CELERY_PREFIX)
class CeleryResultRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,celeryService:CeleryService,configService:ConfigService,jwtService:JWTAuthService):
        super().__init__(None,None)
        self.celeryService:CeleryService = celeryService
        self.configService:ConfigService = configService
        self.jwtAuthService: JWTAuthService = jwtService

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/task/{task_id}/')
    def check_task(self,task_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_result(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/task/{task_id}/')
    def cancel_task(self,task_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return self.celeryService.cancel_task(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/schedule/{schedule_id}/')
    def check_schedule(self,schedule_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_schedule(schedule_id)
        
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/schedule/{schedule_id}/')
    def delete_schedule(self,schedule_id:str,request:Request,authPermission=Depends(get_auth_permission)):
       return  self.celeryService.delete_schedule(schedule_id)
            
    @UseRoles([Role.ADMIN],options=[MustHave(Role.ADMIN)])
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/purge/{queue}/{task_id}/',mount=False)
    def purge_celery_task(self,queue:str, request:Request,task_id:str, authPermission:AuthPermission = Depends(get_auth_permission)):
        """
        Purge a specific task from the celery queue.
        """
        return
    

@UseRoles([Role.RESULT])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@PingService([RedisService])
@HTTPRessource(prefix=BACKGROUND_PREFIX)
class BackgroundTaskRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,redisService:RedisService,configService:ConfigService,taskService:TaskService):
        super().__init__()
        self.redisService = redisService
        self.configService = configService
        self.backgroundTask = taskService
    
    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.Get('/{task_id}/')
    def get_result(self,request:Request,task_id:str,authPermission=Depends(get_auth_permission)):
        ...


@UseRoles([Role.RESULT])
@PingService([TaskService],__task_aps_availability__=True)
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler)
@HTTPRessource(prefix=APS_SCHEDULER)
class APSSchedulerRessource(BaseHTTPRessource):
    configService = Get(ConfigService)

    async def transform_job_to_dict(result:list[Job],request:Request,response:Response):
        return [{'executor':str(x.executor),'name':x.name, 'trigger':str(x.trigger),'coalesce':x.coalesce,"next_run_time":str(x.next_run_time)} for x in result]
    
    @InjectInMethod()
    def __init__(self,configService:ConfigService,taskService:TaskService):
        super().__init__()
        self.configService = configService
        self.taskService = taskService

    @UseHandler(APSSchedulerHandler)
    @UsePipe(transform_job_to_dict,before=False)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.GET],)
    async def get_all_job(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.taskService.get_jobs()
    
    @UseHandler(APSSchedulerHandler)
    @UsePipe(transform_job_to_dict,before=False)
    @BaseHTTPRessource.HTTPRoute('/{job_id}',methods=[HTTPMethod.GET],)
    async def get_job(self,job_id:str,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.taskService.get_jobs(job_id)

    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UsePermission(AdminPermission)
    @UseHandler(APSSchedulerHandler)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.DELETE],)
    async def remove_all_jobs(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.taskService.cancel_job()

    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseHandler(APSSchedulerHandler)
    @BaseHTTPRessource.HTTPRoute('/{job_id}',methods=[HTTPMethod.DELETE],)
    async def remove_job(self,job_id:str,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.taskService.cancel_job(job_id)
            

@HTTPRessource(prefix=RESULT_PREFIX, routers=[CeleryResultRessource,BackgroundTaskRessource,APSSchedulerRessource])
class ResultBackendRessource(BaseHTTPRessource):
    

    @InjectInMethod()
    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__(None,None)
        self.jwtAuthService = jwtAuthService

    @UseHandler(ServiceAvailabilityHandler)
    @UsePermission(JWTRouteHTTPPermission)
    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.Get('/')
    def get_result(self,request:Request,authPermission=Depends(get_auth_permission)):
        return 
    

    @BaseHTTPRessource.Get('/permission/{ws_path}',)
    def invoke_notify_permission(self, ws_path:str,request:Request, authPermission=Depends(get_auth_permission)):
        self._check_ws_path(ws_path)


    async def server_side_event(self):
        ...
    


