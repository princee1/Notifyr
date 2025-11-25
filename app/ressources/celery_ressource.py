from typing import Annotated
from aiohttp_retry import List
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.decorators.pipes import MiniServiceInjectorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseLimiter, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.depends.funcs_dep import get_profile
from app.services.celery_service import CeleryService, ChannelMiniService
from app.services.config_service import ConfigService
from app.services.task_service import TaskService


@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('celery-control')
class CeleryRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,celeryService:CeleryService,configService:ConfigService,taskService:TaskService):
        self.celeryService = celeryService
        self.configService = configService
        self.taskService = taskService

    
    @UseLimiter('1/seconds')
    @UseRoles([Role.PUBLIC])
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/workers/',methods=[HTTPMethod.GET],deprecated=True)
    async def get_all_workers(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter('1/hours')
    @UsePermission(AdminPermission)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/shutdown/',methods=[HTTPMethod.PATCH],deprecated=True)
    async def shutdown_workers(self,destination:List[str], request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter('100/minutes')
    @UseRoles([Role.ADMIN])
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/revoke/',methods=[HTTPMethod.DELETE],deprecated=True)
    async def revoke(self,task_ids:List[str],request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter('1/minutes')
    @UseRoles([Role.PUBLIC])
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/inspect/{mode}/',methods=[HTTPMethod.GET],deprecated=True)
    async def inspect(self,destination:List[str],request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter('10/minutes')
    @UsePermission(AdminPermission)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'))
    @BaseHTTPRessource.HTTPRoute('/purge/{profile}/',methods=[HTTPMethod.DELETE])
    async def purge_queue(self,profile:str,channel:Annotated[ChannelMiniService,Depends(get_profile)], request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        reply = await channel.purge()
        print(reply)