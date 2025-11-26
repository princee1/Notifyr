from typing import Annotated
from fastapi import Depends, Request,status
from app.container import Get, InjectInMethod
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, WebSocketHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.services.celery_service import CeleryService
from app.services.task_service import TaskService
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.security_service import JWTAuthService
from app.depends.dependencies import get_auth_permission
from app.classes.auth_permission import AuthPermission, MustHave, Role


REDIS_EXPIRATION = 360000
RESULT_PREFIX = 'result'

CELERY_PREFIX= 'celery'
BACKGROUND_PREFIX  = 'background'
APS_SCHEDULER='aps'

@UseRoles([Role.REDIS_RESULT])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@PingService([CeleryService])
@HTTPRessource(prefix=CELERY_PREFIX)
class CeleryResultRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,celeryService:CeleryService,configService:ConfigService,jwtService:JWTAuthService):
        super().__init__(None,None)
        self.celeryService:CeleryService = celeryService
        self.configService:ConfigService = configService
        self.jwtAuthService: JWTAuthService = jwtService

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/task/{task_id}')
    def check_task(self,task_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_result(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/task/{task_id}')
    def cancel_task(self,task_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return self.celeryService.cancel_task(task_id)

    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Get('/schedule/{schedule_id}')
    def check_schedule(self,schedule_id:str,request:Request,authPermission=Depends(get_auth_permission)):
        return self.celeryService.seek_schedule(schedule_id)
        
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/schedule/{schedule_id}')
    def delete_schedule(self,schedule_id:str,request:Request,authPermission=Depends(get_auth_permission)):
       return  self.celeryService.delete_schedule(schedule_id)
            
    @UseRoles([Role.ADMIN],options=[MustHave(Role.ADMIN)])
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.Delete('/purge/{queue}/{task_id}',mount=False)
    def purge_celery_task(self,queue:str, request:Request,task_id:str, authPermission:AuthPermission = Depends(get_auth_permission)):
        """
        Purge a specific task from the celery queue.
        """
        return
    

@UseRoles([Role.REDIS_RESULT])
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
    @BaseHTTPRessource.Get('/{task_id}')
    def get_result(self,request:Request,task_id:str,authPermission=Depends(get_auth_permission)):
        ...
    
@HTTPRessource(prefix=APS_SCHEDULER)
class APSSchedulerRessource(BaseHTTPRessource):
    ...


@HTTPRessource(prefix=RESULT_PREFIX, routers=[CeleryResultRessource,BackgroundTaskRessource])
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
    


