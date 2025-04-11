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
from app.ressources.twilio.voice_ressource import CallRessource
#from app.ressources.fax_ressource import FaxRessource
from app.services.twilio_service import TwilioService, VoiceService
from app.utils.helper import APIFilterInject


@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@HTTPRessource('twilio',routers=[SMSRessource,CallRessource])
class TwilioRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,twilioService:TwilioService,voiceService:VoiceService) -> None:
        super().__init__()
        self.twilioService = twilioService
        self.voiceService = voiceService

    @UseLimiter(limit_value= '1000/day')
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/balance/',methods=[HTTPMethod.GET])
    def check_balance(self,request:Request,authPermission=Depends(get_auth_permission)):
        return self.voiceService.fetch_balance()
    
    @UsePipe(parse_phone_number)
    @UseLimiter(limit_value= '10/day')
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/lookup/{phone_number}',methods=[HTTPMethod.GET])
    async def phone_lookup(self,phone_number:str,request:Request,authPermission=Depends(get_auth_permission),carrier:bool=Depends(carrier_info),callee:bool=Depends(callee_info)):
        if not carrier and not carrier:
            raise HTTPException(status_code=400,detail="At least one of carrier or callee must be true")
        
        return await self.twilioService.phone_lookup(phone_number,carrier,callee)
