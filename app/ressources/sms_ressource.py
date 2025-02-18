from typing import Annotated, Any
from fastapi import Depends, Header
from pydantic import BaseModel
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel
from app.decorators.guards import CeleryTaskGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe
from app.definition._ressource import HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import InjectInMethod, InjectInFunction
from app.services.assets_service import AssetService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.twilio_service import SMSService, verify_twilio_token
from app.utils.dependencies import get_auth_permission


SMS_ONGOING_PREFIX = 'sms-ongoing'

class OnGoingSMSModel(BaseModel):
    ...
class SMSTemplateSchedulerModel(SchedulerModel):
    content: Any # TODO


@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_ONGOING_PREFIX)
class OnGoingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, smsService: SMSService,chatService:ChatService,contactService:ContactsService) -> None:
        super().__init__()
        self.smsService: SMSService = smsService
        self.chatService: ChatService = chatService
        self.contactService: ContactsService = contactService
        
    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/')
    def sms_relay_otp(self,authPermission=Depends(get_auth_permission)):
        pass

    @UseLimiter(limit_value='200/minute')
    @BaseHTTPRessource.HTTPRoute('/chat/')
    def sms_chat(self,model:OnGoingSMSModel,authPermission=Depends(get_auth_permission)):
        pass
        
    @UseRoles([Role.RELAY])
    @UsePipe(CeleryTaskPipe)
    @UseGuard(CeleryTaskGuard(['']))
    @UseHandler(CeleryTaskHandler)
    @BaseHTTPRessource.HTTPRoute('/simple/')
    def sms_simple_message(self,scheduler: SMSTemplateSchedulerModel,authPermission=Depends(get_auth_permission)):
        pass
    
    @UseHandler(CeleryTaskHandler)
    @UseRoles([Role.RELAY])
    @UseGuard(CeleryTaskGuard(['']))
    @UsePipe(TemplateParamsPipe('sms'),CeleryTaskPipe)
    @UsePermission(JWTAssetPermission('sms'))
    @BaseHTTPRessource.HTTPRoute('/template/{template}')
    def sms_template(self,template:str,scheduler: SMSTemplateSchedulerModel,authPermission=Depends(get_auth_permission)):
        ...

SMS_INCOMING_PREFIX = "sms-incoming"

@HTTPRessource(SMS_INCOMING_PREFIX )
class IncomingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,contactService:ContactsService) -> None:
        super().__init__(dependencies=[Depends(verify_twilio_token)])
        self.contactService: ContactsService = contactService

    
    @BaseHTTPRessource.HTTPRoute('/chat/')
    def sms_chat(self,authPermission=Depends(get_auth_permission)):
        pass
