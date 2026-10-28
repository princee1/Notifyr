from typing import Annotated
from aiohttp_retry import Callable
from fastapi import Depends, HTTPException, Request
from app.classes.auth_permission import AccessAPIInfo, AuthPermission, ClientAccessInfo, Role
from app.container import GetDependsFunc, InjectInMethod
from app.decorators.handlers import AsyncIOHandler, MiniServiceHandler, ProfileHandler, ServiceAvailabilityHandler, TwilioHandler
from app.decorators.permissions import ClientTypesPermission, JWTRouteHTTPPermission
from app.decorators.pipes import MiniServiceInjectorPipe, parse_phone_number
from app.definition._ressource import HTTPRessource,HTTPMethod,BaseHTTPRessource, PingService, Throttle, UseAccess, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles, LockService
from app.depends.dependencies import get_access_info, get_auth_permission, get_client_info, get_query_params
from app.depends.funcs_dep import get_profile
from app.ressources.twilio.sms_ressource import SMSRessource
from app.ressources.twilio.call_ressource import CallRessource
from app.ressources.twilio.fax_ressource import FaxRessource
from app.services.ntfr.twilio_service import TwilioAccountMiniService, TwilioService, CallService
from app.ressources.twilio.conversation_ressource import ConversationRessource


# ----------------------------------------------                                    ---------------------------------- #


@UseAccess(accesses={'App':True,'User':True,'Admin':True,'System':True})
@UseHandler(ServiceAvailabilityHandler,TwilioHandler,MiniServiceHandler)
@UsePermission(JWTRouteHTTPPermission,ClientTypesPermission(['App','User','Admin','System']))
@HTTPRessource('twilio',routers=[SMSRessource,CallRessource,ConversationRessource,FaxRessource])
class TwilioRessource(BaseHTTPRessource):

    carrier_info:Callable[[Request],bool]=get_query_params('carrier_info','true',True)

    callee_info:Callable[[Request],bool]=get_query_params('callee_info','false',True)

    add_ons:Callable[[Request],bool]=get_query_params('add_ons','false',True)

    parse_to_phone_format: Callable = GetDependsFunc(TwilioService, 'parse_to_phone_format')


    @InjectInMethod()
    def __init__(self,twilioService:TwilioService,callService:CallService) -> None:
        super().__init__()
        self.twilioService = twilioService
        self.callService = callService

    @UseRoles([Role.PUBLIC])
    @Throttle(normal=(100,30))
    @PingService([TwilioService])
    @UseHandler(AsyncIOHandler,ProfileHandler)
    @LockService(TwilioService,as_manager=True)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio'))
    @UseLimiter(limit_value= '100/day',cost={'App':10,'User':2})
    @BaseHTTPRessource.HTTPRoute('/balance/{profile}/',methods=[HTTPMethod.GET])
    async def check_balance(self,profile:str,twilio:Annotated[TwilioAccountMiniService,Depends(get_profile)],request:Request,authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        return await twilio.fetch_balance()
    
    @UseRoles([Role.PUBLIC])
    @Throttle(normal=(100,30))
    @UsePipe(parse_phone_number)
    @PingService([TwilioService])
    @UseLimiter(limit_value= '10/day')
    @BaseHTTPRessource.HTTPRoute('/lookup/{phone_number}',methods=[HTTPMethod.GET])
    async def phone_lookup(self,phone_number:str,request:Request,carrier:Annotated[bool,Depends(carrier_info)],callee:Annotated[bool,Depends(callee_info)],authPermission:AuthPermission=Depends(get_auth_permission), clientInfo:ClientAccessInfo = Depends(get_client_info), accessInfo:AccessAPIInfo = Depends(get_access_info) ):
        if not carrier and not callee:
            raise HTTPException(status_code=400,detail="At least one of carrier or callee must be true")
        
        status_code, body = await self.twilioService.phone_lookup(phone_number,True,True)
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=body)
        
        return body
