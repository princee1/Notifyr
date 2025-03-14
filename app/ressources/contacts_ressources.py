

from typing import Annotated
from fastapi import Depends, HTTPException, Query, Request, status
from app.classes.auth_permission import AuthPermission, ContactPermission, MustHave, Role
from app.classes.celery import CeleryTask, TaskHeaviness
from app.classes.template import Template
from app.container import Get, GetDependsAttr, InjectInMethod
from app.decorators.guards import ActiveContactGuard, ContactActionCodeGuard, RegisteredContactsGuard
from app.decorators.handlers import ContactsHandler, TemplateHandler, TortoiseHandler
from app.decorators.permissions import JWTContactPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles
from app.models.contacts_model import ContactORM,ContactModel, ContentTypeSubsModel, SubsContentORM
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.contacts_service import MAX_OPT_IN_CODE, MIN_OPT_IN_CODE, ContactsService, SubscriptionService
from app.services.email_service import EmailSenderService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.twilio_service import SMSService, TwilioService, VoiceService
from app.utils.dependencies import get_auth_permission
from app.decorators.pipes import ContactsIdPipe, RelayPipe
from pydantic import BaseModel


verify_twilio_token = GetDependsAttr(TwilioService,'verify_twilio_token')

SUBSCRIPTION_PREFIX = 'subscription'

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
    async def register_subscription(self,):
        ...

    @BaseHTTPRessource.Delete('/')
    async def delete_subscription(self):
        ...
    
    @BaseHTTPRessource.Get('/')
    async def get_subscription(self):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT])
    async def update_subscription(self):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/ttl',methods=[HTTPMethod.PUT])
    async def update_subscription_ttl(self):
        ...

##############################################                   ##################################################
CONTACTS_PREFIX = 'contacts'
CONTACTS_SECURITY_PREFIX = 'security'
CONTACTS_SUBSCRIPTION_PREFIX = 'subscription'

async def get_contacts(contact_id: str, idtype: str = Query("id"),authPermission:AuthPermission=Depends(get_auth_permission)) -> ContactORM:

    if Role.CONTACTS not in authPermission['roles']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role not allowed")
        
    match idtype:
        case "id":
            user = await ContactORM.filter(contact_id=contact_id).first()

        case "phone":
            user = await ContactORM.filter(phone=contact_id).first()

        case "email":
            user = await ContactORM.filter(email=contact_id).first()

        case _:
            raise HTTPException(
                400,{"message": "idtype not not properly specified"})

    if user == None:
        raise HTTPException(404, {"detail": "user does not exists"})

    return user

def get_contact_permission(token:str= Query(None))->ContactPermission:

    jwtAuthService:JWTAuthService = Get(JWTAuthService)
    if token == None:
        raise # TODO 
    return jwtAuthService.verify_contact_permission(token)

def get_subs_content(content_id:str,idtype:str = Query('id'),authPermission:AuthPermission=Depends(get_auth_permission))->SubsContentORM:

    if Role.CONTACTS not in authPermission['roles']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Role not allowed")
    
    match idtype:
        case "id":
            content = SubsContentORM.filter(content_id=content_id).first()
        case "name":
            content = SubsContentORM.filter(name=content_id).first()
        case _:
            raise HTTPException(
                400,{"message": "idtype not not properly specified"})
    
    if content == None:
        raise HTTPException(404, {"message": "Subscription Content does not exists with those information"})

            

##############################################                   ##################################################


@UseHandler(ContactsHandler)
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
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}')
    async def unsubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)],action_code=Query(None), authPermission=Depends(get_auth_permission)):
        #TODO  Inactive will not delete the contact subscription 
        #NOTE what to do when Blacklist ?

       # TODO set a new opt-in code
       # TODO delete  the contact subscription status if back to pending
       # TODO set the user status back to Pending or Inactive
       # TODO Delete all subscription
       # TODO Delete content_type_subscription if back to pending
       ...

    @UseGuard(ContactActionCodeGuard)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def resubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)],action_code:str=Query(None), authPermission=Depends(get_auth_permission)):
        # TODO if inactive set back to Active otherwise cant do None,
        ...

    @UsePipe(RelayPipe(False))
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-subscribe/{contact_id}',[HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def content_subscribe(self,contact: Annotated[ContactORM, Depends(get_contacts)], subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],relay:str = Query(None), authPermission=Depends(get_auth_permission)):
        # TODO if its okay add subscription
        ...
    
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-preferences/{contact_id}',[HTTPMethod.POST])
    async def toggle_content_type_preferences(self,flags_content_types:ContentTypeSubsModel,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        await self.contactService.toggle_content_type_subs_flag(contact,flags_content_types)

    @UseGuard(ContactActionCodeGuard(True)) # NOTE the server can bypass the action_code guard only if the subs_content is notification or update
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.Delete('/content-unsubscribe/{contact_id}')
    async def content_unsubscribe(self,contact: Annotated[ContactORM, Depends(get_contacts)],subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],action_code:str=Query(None),authPermission=Depends(get_auth_permission)):
        ...

    @UseGuard(ContactActionCodeGuard(True))  # NOTE the server can bypass the action_code guard only if the subs_content is notification or update
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-status/{contact_id}',[HTTPMethod.POST])
    async def update_content_subscription(self,contact: Annotated[ContactORM, Depends(get_contacts)],subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],action_code:str=Query(None),authPermission=Depends(get_auth_permission)):
        ...

    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.Get('/{contact_id}')
    async def get_contact_subscription(self,contact: Annotated[ContactORM, Depends(get_contacts)],subs_content:Annotated[SubsContentORM,Depends(get_subs_content)],authPermission=Depends(get_auth_permission)):
        return await self.subscriptionService.get_contact_subscription(contact.contact_id,subs_content.content_id)


@UseHandler(ContactsHandler)
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


@UseHandler(ContactsHandler)
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
       return await self.contactsService.activate_newsletter_contact(contact,opt)
        
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
