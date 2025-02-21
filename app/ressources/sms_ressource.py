from typing import Annotated, Any
from fastapi import Depends, Header
from pydantic import BaseModel
from app.classes.auth_permission import Role
from app.classes.celery import SchedulerModel
from app.decorators.guards import CeleryTaskGuard
from app.decorators.handlers import CeleryTaskHandler, ServiceAvailabilityHandler, TwilioHandler
from app.decorators.permissions import JWTAssetPermission,JWTRouteHTTPPermission
from app.decorators.pipes import CeleryTaskPipe, TemplateParamsPipe
from app.definition._ressource import HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, UsePipe, UseRoles
from app.container import InjectInMethod, InjectInFunction
from app.models.otp_model import OTPModel
from app.services.assets_service import AssetService
from app.services.chat_service import ChatService
from app.services.contacts_service import ContactsService
from app.services.twilio_service import SMSService
from app.utils.dependencies import get_auth_permission


SMS_ONGOING_PREFIX = 'sms-ongoing'

class OnGoingSMSModel(BaseModel):
    ...

class SMSSchedulerModel(SchedulerModel):
    content: Any # TODO


@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_ONGOING_PREFIX)
class OnGoingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self, smsService: SMSService,assetService:AssetService,chatService:ChatService) -> None:
        self.smsService: SMSService = smsService
        self.assetService: AssetService = assetService
        self.chatService: ChatService = chatService

        super().__init__(dependencies=[Depends(self.smsService.verify_twilio_token)])

        
    @UseRoles([Role.MFA_OTP])
    @BaseHTTPRessource.HTTPRoute('/otp/')
    def sms_relay_otp(self,otpModel:OTPModel,authPermission=Depends(get_auth_permission)):
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
    def sms_simple_message(self,scheduler: SMSSchedulerModel,authPermission=Depends(get_auth_permission)):
        pass
    
    @UseHandler(CeleryTaskHandler)
    @UseRoles([Role.RELAY])
    @UseGuard(CeleryTaskGuard(['']))
    @UsePipe(TemplateParamsPipe('sms'),CeleryTaskPipe)
    @UsePermission(JWTAssetPermission('sms'))
    @BaseHTTPRessource.HTTPRoute('/template/{template}')
    def sms_template(self,template:str,scheduler: SMSSchedulerModel,authPermission=Depends(get_auth_permission)):
        ...



SMS_INCOMING_PREFIX = "sms-incoming"

@UseRoles([Role.TWILIO])
@PingService([SMSService])
@UseHandler(ServiceAvailabilityHandler,TwilioHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(SMS_INCOMING_PREFIX )
class IncomingSMSRessource(BaseHTTPRessource):
    @InjectInMethod
    def __init__(self,smsService:SMSService,contactsService:ContactsService,chatService:ChatService) -> None:
        self.smsService: SMSService = smsService
        self.contactsService: ContactsService = contactsService
        self.chatService: ChatService = chatService
        super().__init__(dependencies=[Depends(self.smsService.verify_twilio_token)])

    @BaseHTTPRessource.HTTPRoute('/menu/',methods=['POST'])
    async def sms_menu(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @UseRoles([Role.CHAT])
    @BaseHTTPRessource.HTTPRoute('/live-chat/',methods=['POST'])
    async def sms_chat(self,authPermission=Depends(get_auth_permission)):
        pass

    @BaseHTTPRessource.HTTPRoute('/automate-response/',methods=['POST'])
    async def sms_automated(self,authPermission=Depends(get_auth_permission)):
        pass
    
    @BaseHTTPRessource.HTTPRoute('/handler_fail/',methods=['POST'])
    async def sms_primary_handler_fail(self,authPermission=Depends(get_auth_permission)):
        pass
