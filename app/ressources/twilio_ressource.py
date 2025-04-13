from typing import Annotated
from fastapi import Depends, HTTPException, Request
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.handlers import ServiceAvailabilityHandler, TwilioHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import parse_phone_number
from app.definition._ressource import HTTPRessource,HTTPMethod,BaseHTTPRessource, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.depends.dependencies import get_auth_permission
from app.depends.variables import parse_to_phone_format,carrier_info,callee_info
from app.ressources.twilio.sms_ressource import SMSRessource
from app.ressources.twilio.call_ressource import CallRessource
#from app.ressources.fax_ressource import FaxRessource
from app.services.twilio_service import TwilioService, CallService


@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@HTTPRessource('twilio',routers=[SMSRessource,CallRessource])
class TwilioRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,twilioService:TwilioService,callService:CallService) -> None:
        super().__init__()
        self.twilioService = twilioService
        self.callService = callService

    @UseLimiter(limit_value= '1000/day')
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/balance/',methods=[HTTPMethod.GET])
    def check_balance(self,request:Request,authPermission=Depends(get_auth_permission)):
        return self.callService.fetch_balance()
    
    @UsePipe(parse_phone_number)
    @UseLimiter(limit_value= '10/day')
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/lookup/{phone_number}',methods=[HTTPMethod.GET])
    async def phone_lookup(self,phone_number:str,request:Request,carrier:Annotated[bool,Depends(carrier_info)],callee:Annotated[bool,Depends(callee_info)],authPermission=Depends(get_auth_permission)):
        if not carrier and not callee:
            raise HTTPException(status_code=400,detail="At least one of carrier or callee must be true")
        
        status_code, body = await self.twilioService.async_phone_lookup(phone_number,True,True)
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=body)
        return body
