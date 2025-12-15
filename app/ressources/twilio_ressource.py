from typing import Annotated
from fastapi import Depends, HTTPException, Request
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, MiniServiceHandler, ProfileHandler, ServiceAvailabilityHandler, TwilioHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import MiniServiceInjectorPipe, parse_phone_number
from app.definition._ressource import HTTPRessource,HTTPMethod,BaseHTTPRessource, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.depends.dependencies import get_auth_permission
from app.depends.funcs_dep import get_profile
from app.depends.variables import parse_to_phone_format,carrier_info,callee_info
from app.ressources.twilio.sms_ressource import SMSRessource
from app.ressources.twilio.call_ressource import CallRessource
from app.ressources.twilio.fax_ressource import FaxRessource
from app.services.twilio_service import TwilioAccountMiniService, TwilioService, CallService
from app.ressources.twilio.conversation_ressource import ConversationRessource


@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,TwilioHandler,MiniServiceHandler)
@HTTPRessource('twilio',routers=[SMSRessource,CallRessource,ConversationRessource,FaxRessource])
class TwilioRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,twilioService:TwilioService,callService:CallService) -> None:
        super().__init__()
        self.twilioService = twilioService
        self.callService = callService

    @PingService([TwilioService])
    @UseLimiter(limit_value= '1000/day')
    @UseRoles([Role.PUBLIC])
    @UseHandler(AsyncIOHandler,ProfileHandler)
    @UsePipe(MiniServiceInjectorPipe(TwilioService,'twilio'))
    @UseServiceLock(TwilioService,as_manager=True)
    @BaseHTTPRessource.HTTPRoute('/balance/{profile}/',methods=[HTTPMethod.GET])
    async def check_balance(self,profile:str,twilio:Annotated[TwilioAccountMiniService,Depends(get_profile)],request:Request,authPermission=Depends(get_auth_permission)):
        return await twilio.fetch_balance()
    
    @PingService([TwilioService])
    @UsePipe(parse_phone_number)
    @UseLimiter(limit_value= '10/day')
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/lookup/{phone_number}',methods=[HTTPMethod.GET])
    async def phone_lookup(self,phone_number:str,request:Request,carrier:Annotated[bool,Depends(carrier_info)],callee:Annotated[bool,Depends(callee_info)],authPermission=Depends(get_auth_permission)):
        if not carrier and not callee:
            raise HTTPException(status_code=400,detail="At least one of carrier or callee must be true")
        
        status_code, body = await self.twilioService.phone_lookup(phone_number,True,True)
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=body)
        
        return body
