

from typing import Annotated
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from app.classes.auth_permission import MustHave, Role
from app.container import Get,InjectInMethod
from app.decorators.guards import ActiveContactGuard, ContactActionCodeGuard, RegisteredContactsGuard
from app.decorators.handlers import ContactsHandler, TemplateHandler, TortoiseHandler
from app.decorators.my_depends import get_contact_permission, get_contacts, get_subs_content,verify_twilio_token
from app.decorators.permissions import JWTContactPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles
from app.models.contacts_model import ContactORM,ContactModel, ContentTypeSubsModel, Status, SubsContentORM, SubscriptionStatus
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.contacts_service import MAX_OPT_IN_CODE, MIN_OPT_IN_CODE, ContactsService, SubscriptionService
from app.services.email_service import EmailSenderService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.twilio_service import SMSService, VoiceService
from app.utils.dependencies import get_auth_permission
from app.decorators.pipes import ContactStatusPipe, RelayPipe


CONTACTS_PREFIX = 'contacts'
CONTACTS_SECURITY_PREFIX = 'security'
CONTACTS_SUBSCRIPTION_PREFIX = 'subscription'
       
##############################################                   ##################################################


SUBSCRIPTION_PREFIX = 'subscription'

@UseHandler(TortoiseHandler)
@UsePermission(JWTRouteHTTPPermission)
@UseRoles([Role.SUBSCRIPTION])
@HTTPRessource(SUBSCRIPTION_PREFIX)
class SubscriptionRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,contactsService:ContactsService,subscriptionService:SubscriptionService):
        super().__init__()
        self.contactsService = contactsService
        self.subscriptionService = subscriptionService
    
    @BaseHTTPRessource.Post('/')
    async def register_subscription(self,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Delete('/')
    async def delete_subscription(self,subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],authPermission=Depends(get_auth_permission)):
        ...
    
    @BaseHTTPRessource.Get('/')
    async def get_subscription(self,subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT])
    async def update_subscription(self,subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],authPermission=Depends(get_auth_permission)):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/ttl',methods=[HTTPMethod.PUT])
    async def update_subscription_ttl(self,subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],authPermission=Depends(get_auth_permission)):
        ...

##############################################                   ##################################################

@UseHandler(TortoiseHandler,ContactsHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@PingService([ContactsService])
@HTTPRessource(CONTACTS_SUBSCRIPTION_PREFIX)
class ContactsSubscriptionRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,contactService:ContactsService,subscriptionService:SubscriptionService):
        super().__init__()
        self.contactService = contactService
        self.subscriptionService = subscriptionService

    @UseRoles([Role.RELAY])
    @UseGuard(ContactActionCodeGuard)
    @UseGuard(ActiveContactGuard)
    @UseHandler(TemplateHandler)
    @UsePipe(ContactStatusPipe)
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}')
    async def unsubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)],action_code=Query(None),next_status:Status= Query(None), authPermission=Depends(get_auth_permission)):
        if next_status == Status.Active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="Next status cannot to Active be set when unsubscribing to the contact")
        
        return await self.contactService.unsubscribe_contact(contact,next_status)

    @UseGuard(ContactActionCodeGuard)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def resubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)],action_code:str=Query(None),authPermission=Depends(get_auth_permission)):
        if contact.status == Status.Active:
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED,content='Nothing to do')
        
        if contact.status == Status.Inactive or contact.status == Status.Blacklist:
            contact.status = Status.Active
            await contact.save()
            return JSONResponse('Re activated the contacts back to active',status_code=status.HTTP_200_OK)
        
        return JSONResponse("You must re activate your account with your new opt-int",status_code = status.HTTP_423_LOCKED)

    @UsePipe(RelayPipe(False))
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-subscribe/{contact_id}',[HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def content_subscribe(self,contact: Annotated[ContactORM, Depends(get_contacts)], subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],relay:str = Query(None), authPermission=Depends(get_auth_permission)):
        return await self.subscriptionService.subscribe_user(contact,subs_content,relay)
        
    
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-preferences/{contact_id}',[HTTPMethod.POST])
    async def toggle_content_type_preferences(self,flags_content_types:ContentTypeSubsModel,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        await self.contactService.toggle_content_type_subs_flag(contact,flags_content_types)

    @UseGuard(ContactActionCodeGuard(True)) # NOTE the server can bypass the action_code guard only if the subs_content is notification or update
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.Delete('/content-unsubscribe/{contact_id}')
    async def content_unsubscribe(self,contact: Annotated[ContactORM, Depends(get_contacts)],subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],action_code:str=Query(None),authPermission=Depends(get_auth_permission)):
        return await self.subscriptionService.unsubscribe_user(contact,subs_content)

    @UseGuard(ContactActionCodeGuard(True))  # NOTE the server can bypass the action_code guard only if the subs_content is notification or update
    @UseGuard(ActiveContactGuard)
    @UsePipe(RelayPipe)
    @BaseHTTPRessource.HTTPRoute('/content-status/{contact_id}',[HTTPMethod.POST])
    async def update_content_subscription(self,contact: Annotated[ContactORM, Depends(get_contacts)],subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],relay:str = Query(None),action_code:str=Query(None),next_subs_status:SubscriptionStatus=Query(None),authPermission=Depends(get_auth_permission)):
        if not next_subs_status:
            return JSONResponse(content='',status_code=status.HTTP_400_BAD_REQUEST)
        
        return await self.subscriptionService.update_subscription(contact,subs_content,relay,next_subs_status)

    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.Get('/{contact_id}')
    async def get_contact_subscription(self,contact: Annotated[ContactORM, Depends(get_contacts)],subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],authPermission=Depends(get_auth_permission)):
        return await self.subscriptionService.get_contact_subscription(contact.contact_id,subs_content.content_id)


@UseHandler(TortoiseHandler,ContactsHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@PingService([ContactsService])
@HTTPRessource(CONTACTS_SECURITY_PREFIX)
class ContactSecurityRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,securityService:SecurityService,jwtService:JWTAuthService,contactsService:ContactsService,celeryService:CeleryService ):
        super().__init__()
        self.securityService = securityService
        self.jwtAuthService = jwtService
        self.contactService = contactsService
        self.celeryService = celeryService
    
    @UseGuard(RegisteredContactsGuard)
    @UseRoles(options=[MustHave(Role.TWILIO)])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.GET],dependencies=[Depends(verify_twilio_token)])
    async def check_password(self,contact: Annotated[ContactORM, Depends(get_contacts)],request:Request,authPermission=Depends(get_auth_permission)):
        ...

    @UsePermission(JWTContactPermission('update'))
    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PUT])
    async def update_raw_contact_security(self, contact: Annotated[ContactORM, Depends(get_contacts)],token:str= Query(None),contactPermission=Depends(get_contact_permission), authPermission=Depends(get_auth_permission)):
        # BUG cant update without having in set up before
        ...

    @UsePermission(JWTContactPermission('create'))
    @UseGuard(RegisteredContactsGuard)
    @PingService([CeleryService,VoiceService,EmailSenderService])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.POST])
    async def create_contact_security(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Query(None), contactPermission=Depends(get_contact_permission), authPermission=Depends(get_auth_permission)):
        # TODO update token permission after use
        ...
    
    @UsePermission(JWTContactPermission('update'))
    @UseGuard(RegisteredContactsGuard)
    @PingService([CeleryService,VoiceService,EmailSenderService])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PATCH])
    async def update_contact_security(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Query(None),forgot:bool=Query(False), contactPermission=Depends(get_contact_permission),  authPermission=Depends(get_auth_permission)):
        # TODO update token permission after use
        ...


    @UsePipe(RelayPipe)
    @UseGuard(RegisteredContactsGuard)
    @PingService([ContactsService])
    @BaseHTTPRessource.HTTPRoute('/token/{contact_id}',[HTTPMethod.GET])
    async def get_token_link(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        return 


    @UsePipe(RelayPipe)
    @UseGuard(RegisteredContactsGuard)
    @PingService([CeleryService,VoiceService,EmailSenderService,ContactsService])
    @BaseHTTPRessource.HTTPRoute('/token/{contact_id}',[HTTPMethod.POST])
    async def request_new_token_link(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        ...

    @UsePipe(RelayPipe)
    @UseHandler(TemplateHandler)
    @UseRoles([Role.RELAY])
    @UseGuard(RegisteredContactsGuard)
    @PingService([ContactsService])
    @BaseHTTPRessource.HTTPRoute('/token/{contact_id}',[HTTPMethod.PATCH])
    async def update_token(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        ...


@UseHandler(TortoiseHandler,ContactsHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@PingService([ContactsService])
@HTTPRessource(CONTACTS_PREFIX,routers= [ContactSecurityRessource,ContactsSubscriptionRessource])
class ContactsRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, contactsService: ContactsService, celeryService: CeleryService, bkgTaskService: BackgroundTaskService,emailService:EmailSenderService,smsService:SMSService):
        super().__init__()
        self.contactsService = contactsService
        self.celeryService = celeryService
        self.bkgTaskService = bkgTaskService
        self.from_ = Get(ConfigService).getenv('TWILIO_OTP_NUMBER')

    @UseHandler(TemplateHandler)
    @BaseHTTPRessource.Post('/activate/{contact_id}')
    async def activate_contact(self,contact: Annotated[ContactORM, Depends(get_contacts)],opt:int = Query(ge=MIN_OPT_IN_CODE,le=MAX_OPT_IN_CODE),authPermission=Depends(get_auth_permission)):
       return await self.contactsService.activate_contact(contact,opt)
        
    @UsePipe(RelayPipe)
    @UseRoles([Role.RELAY])
    @UseHandler(TemplateHandler)
    @BaseHTTPRessource.Post('/{relay}')
    async def create_contact(self, relay: str, contact:ContactModel,authPermission=Depends(get_auth_permission)):
        #NOTE  if app registered send a jwt token for changing his security shit
        return await self.contactsService.create_new_contact(contact)
    
    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Get('/{contact_id}')
    async def read_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        return await self.contactsService.read_contact(contact.contact_id)

    @BaseHTTPRessource.HTTPRoute('/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT])
    async def update_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Delete('/{contact_id}')
    async def delete_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        return await contact.delete()

    @BaseHTTPRessource.Get('/all')
    async def get_all_contacts(self,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Get('/file')
    async def import_contacts(self,authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Post('/file')
    async def export_contacts(self,authPermission=Depends(get_auth_permission)):
        ...


##############################################                   ##################################################
