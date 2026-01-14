from typing import Annotated, Callable, get_args
from aiohttp_retry import List
from fastapi import Depends, HTTPException, Request, Response,status
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, CeleryControlHandler, MiniServiceHandler, ProfileHandler, ServiceAvailabilityHandler
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission
from app.decorators.pipes import MiniServiceInjectorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.depends.dependencies import get_auth_permission, get_query_params
from app.depends.funcs_dep import get_profile
from app.services.worker.celery_service import CeleryService, ChannelMiniService, InspectMode
from app.services.config_service import ConfigService
from app.services.worker.task_service import TaskService
from app.depends.variables import _wrap_checker

@PingService([{"cls":CeleryService,"kwargs":{"__celery_availability__":True}}])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,ProfileHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('celery-control')
class CeleryRessource(BaseHTTPRessource):

    celery_inspect_mode_query:Callable[[Request],str] = get_query_params('mode','stats',False,raise_except=True,checker=_wrap_checker('mode',lambda m:m in get_args(InspectMode),choices=list(get_args(InspectMode))))


    @InjectInMethod()
    def __init__(self,celeryService:CeleryService,configService:ConfigService,taskService:TaskService):
        super().__init__()
        self.celeryService = celeryService
        self.configService = configService
        self.taskService = taskService
    
    @UseLimiter('1/seconds')
    @UseRoles([Role.PUBLIC])
    @UseHandler(CeleryControlHandler)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/ping/',methods=[HTTPMethod.GET])
    async def ping_workers(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.celeryService.ping()
    
    @UseLimiter('1/minutes')
    @UseRoles([Role.PUBLIC])
    @UseHandler(CeleryControlHandler)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/inspect/',methods=[HTTPMethod.GET])
    async def inspect(self,request:Request,response:Response,mode:InspectMode = Depends(celery_inspect_mode_query),authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.celeryService.inspect(mode)

    @UseLimiter('10/minutes')
    @UsePermission(AdminPermission)
    @UseHandler(MiniServiceHandler,CeleryControlHandler)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'))
    @BaseHTTPRessource.HTTPRoute('/purge/{profile}/',methods=[HTTPMethod.DELETE])
    async def purge_queue(self,profile:str,channel:Annotated[ChannelMiniService,Depends(get_profile)], request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await channel.purge_queue()
        
    ################################################################        ############################################################
    #                                                        Non-Mounted Route                                                         #
    ################################################################        ############################################################

    @UseLimiter('1/hours')
    @UsePermission(AdminPermission)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/shutdown/',methods=[HTTPMethod.PATCH],deprecated=True,mount=False)
    async def shutdown_workers(self,destination:List[str], request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.celeryService.shutdown()

    @UseLimiter('100/minutes')
    @UseRoles([Role.ADMIN])
    @UseServiceLock(CeleryService,lockType='reader',check_status=False)
    @BaseHTTPRessource.HTTPRoute('/revoke/',methods=[HTTPMethod.DELETE],deprecated=True,mount=False)
    async def revoke(self,task_ids:List[str],request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseLimiter('1/minutes')
    @UsePermission(AdminPermission)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'))
    @BaseHTTPRessource.HTTPRoute('/pause/{profile}/',methods=[HTTPMethod.DELETE],mount=False)
    async def pause_queue(self,channel:Annotated[ChannelMiniService,Depends(get_profile)], request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        await channel.pause_worker()

    @UseLimiter('1/minutes')
    @UsePermission(AdminPermission)
    @UseServiceLock(CeleryService,lockType='reader',check_status=False,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'))
    @BaseHTTPRessource.HTTPRoute('/resume/{profile}/',methods=[HTTPMethod.PATCH],mount=False)
    async def resume_queue(self,channel:Annotated[ChannelMiniService,Depends(get_profile)], request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...