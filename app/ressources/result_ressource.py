from typing import Annotated
from fastapi import Depends, Request, Response,status
from app.container import Get, InjectInMethod
from app.decorators.handlers import APSSchedulerHandler, AsyncIOHandler, CeleryTaskHandler, RedisHandler, ServiceAvailabilityHandler, WebSocketHandler
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.services.celery_service import CeleryService
from app.services.database.redis_service import RedisService
from app.services.task_service import TaskService
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.depends.dependencies import get_auth_permission
from app.classes.auth_permission import AuthPermission, MustHave, Role
from apscheduler.job import Job

from app.utils.constant import APSchedulerConstant, CeleryConstant, RedisConstant


REDIS_EXPIRATION = 360000
RESULT_PREFIX = 'result'

CELERY_PREFIX= 'celery'
BACKGROUND_PREFIX  = 'background'
APS_SCHEDULER='aps'

@UseRoles([Role.RESULT])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@PingService([{"cls":CeleryService,"kwargs":{"__celery_availability__":True}}])
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
    async def check_task(self,task_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return await self.celeryService.seek_result(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/task/{task_id}/')
    async def cancel_task(self,task_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return await self.celeryService.cancel_task(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/schedule/{schedule_id}/{index}')
    async def check_schedule(self,schedule_id:str,index:int,request:Request,authPermission=Depends(get_auth_permission)):
        return await self.celeryService.seek_schedule(schedule_id,index)
        
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/schedule/{schedule_id}/{index}')
    async def delete_schedule(self,schedule_id:str,index:int,request:Request,authPermission=Depends(get_auth_permission)):
       return await self.celeryService.delete_schedule(schedule_id,index)
    
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/reschedule/{schedule_id}/{index}')
    async def delete_schedule(self,schedule_id:str,index:int,request:Request,authPermission=Depends(get_auth_permission)):
       return await self.celeryService.delete_schedule(schedule_id,index)
            
    @UseRoles([Role.ADMIN],options=[MustHave(Role.ADMIN)])
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/purge/{queue}/{task_id}/',mount=False)
    async def purge_celery_task(self,queue:str, request:Request,task_id:str, authPermission:AuthPermission = Depends(get_auth_permission)):
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
    def __init__(self,redisService:RedisService,configService:ConfigService):
        super().__init__()
        self.redisService = redisService
        self.configService = configService
    
    @UseHandler(RedisHandler)
    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.Get('/{task_id}')
    async def get_result(self,request:Request,task_id:str,authPermission=Depends(get_auth_permission)):
        task_id = CeleryConstant.REDIS_BKG_TASK_ID_RESOLVER(task_id)
        return await self.redisService.hash_get(RedisConstant.CELERY_DB,task_id)
    

@UseRoles([Role.RESULT])
@PingService([{"cls":TaskService,"kwargs":{"__task_aps_availability__":True}}])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler)
@HTTPRessource(prefix=APS_SCHEDULER)
class APSSchedulerRessource(BaseHTTPRessource):
    configService = Get(ConfigService)

    async def transform_job_to_dict(result:list[Job],request:Request,response:Response):
        return [{'executor':str(x.executor),'name':x.name, 'trigger':str(x.trigger),'coalesce':x.coalesce,"next_run_time":str(x.next_run_time),'job_id':x.id} for x in result]
    
    @InjectInMethod()
    def __init__(self,configService:ConfigService,taskService:TaskService):
        super().__init__()
        self.configService = configService
        self.taskService = taskService

    @UseHandler(APSSchedulerHandler)
    @UsePipe(transform_job_to_dict,before=False)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.GET],)
    async def get_all_job(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        jobs:list[Job] =  await self.taskService.get_jobs()
        return [j for j in jobs if str(j.id).startswith(CeleryConstant.BACKEND_KEY_PREFIX)]
    
    @UseHandler(APSSchedulerHandler)
    @UsePipe(transform_job_to_dict,before=False)
    @BaseHTTPRessource.HTTPRoute('/{request_id}/{index}/',methods=[HTTPMethod.GET],)
    async def get_job(self,request_id:str,index:int,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        job_id = APSchedulerConstant.REDIS_APS_ID_RESOLVER(request_id,index)
        return await self.taskService.get_jobs(job_id)

    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UsePermission(AdminPermission)
    @UseHandler(APSSchedulerHandler)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.DELETE],mount=True)
    async def remove_all_jobs(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        jobs:list[Job] = await self.taskService.get_jobs()
        result = []
        for j in jobs:
            job_id:str = j.id
            if job_id.startswith(CeleryConstant.BACKEND_KEY_PREFIX):
                await self.taskService.cancel_job(job_id)
                result.append(j)
        return result

    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseHandler(APSSchedulerHandler)
    @BaseHTTPRessource.HTTPRoute('/{request_id}/{index}/',methods=[HTTPMethod.DELETE],)
    async def remove_job(self,request_id:str,index:int,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        job_id = APSchedulerConstant.REDIS_APS_ID_RESOLVER(request_id,index)
        return await self.taskService.cancel_job(job_id)

    @UsePermission(AdminPermission)
    @UseHandler(APSSchedulerHandler)
    @BaseHTTPRessource.HTTPRoute('/{request_id}/{index}/',methods=[HTTPMethod.PATCH],)
    async def pause_job(self,request_id:str,index:int,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        job_id = APSchedulerConstant.REDIS_APS_ID_RESOLVER(request_id,index)
        return await self.taskService.pause_job(job_id)

    @UsePermission(AdminPermission)
    @UseHandler(APSSchedulerHandler)
    @BaseHTTPRessource.HTTPRoute('/{request_id}/{index}/',methods=[HTTPMethod.PUT],)
    async def resume_job(self,request_id:str,index:int,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        job_id = APSchedulerConstant.REDIS_APS_ID_RESOLVER(request_id,index)
        return await self.taskService.resume_job(job_id)
            

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
    


