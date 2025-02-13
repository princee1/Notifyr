from typing import Annotated
from fastapi import Depends, Header
from app.classes.auth_permission import Role
from app.decorators.guards import CeleryTaskGuard
from app.decorators.handlers import ServiceAvailabilityHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe
from app.definition._ressource import HTTPRessource, UseGuard, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import InjectInMethod, InjectInFunction
from app.services.assets_service import AssetService
from app.services.chat_service import ChatService
from app.services.twilio_service import SMSService, verify_twilio_token
from app.utils.dependencies import get_auth_permission


SMS_ONGOING_PREFIX = 'sms-ongoing'

@UseRoles([Role.CHAT,Role.RELAY])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_ONGOING_PREFIX)
class OnGoingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, smsService: SMSService,assetService:AssetService,chatService:ChatService) -> None:
        super().__init__()
        self.smsService: SMSService = smsService
        self.assetService: AssetService = assetService
        self.chatService: ChatService = chatService
        

    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/')
    def sms_relay_otp(self,authPermission=Depends(get_auth_permission)):
        pass
        
    @BaseHTTPRessource.HTTPRoute('/simple/')
    def sms_simple_message(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @UsePipe(TemplateParamsPipe('sms'))
    @UsePermission(JWTAssetPermission('html'))
    @BaseHTTPRessource.HTTPRoute('/template/{template}')
    def sms_template(self,template:str,authPermission=Depends(get_auth_permission)):
        ...

SMS_INCOMING_PREFIX = "sms-incoming"

@HTTPRessource(SMS_INCOMING_PREFIX )
class IncomingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,) -> None:
        super().__init__(depends=[Depends(verify_twilio_token)])

    
    @BaseHTTPRessource.HTTPRoute('/chat/')
    def sms_chat(self,authPermission=Depends(get_auth_permission)):
        pass