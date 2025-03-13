

from typing import Annotated
from fastapi import Depends, HTTPException, Query, Request, status
from app.classes.auth_permission import AuthPermission, ContactPermission, MustHave, Role
from app.classes.celery import CeleryTask, TaskHeaviness
from app.classes.template import Template
from app.container import Get, GetDependsAttr, InjectInMethod
from app.decorators.guards import RegisteredContactsGuard
from app.decorators.handlers import ContactsHandler, TemplateHandler, TortoiseHandler
from app.decorators.permissions import JWTContactPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles
from app.models.contacts_model import ContactORM,ContactModel
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService, SubscriptionService
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
    
    async def register_subscription(self,):
        ...

    async def delete_subscription(self):
        ...
    
    async def get_subscription(self):
        ...

    async def update_subscription(self):
        ...
    
    async def update_subscription_ttl(self):
        ...

    
    

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
    

@UseHandler(ContactsHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@PingService([ContactsService])
@HTTPRessource(CONTACTS_SUBSCRIPTION_PREFIX)
class ContactsSubscriptionRessource(BaseHTTPRessource):

    def __init__(self,contactService:ContactsService,subscriptionService:SubscriptionService):
        self.contactService = contactService
        self.subscriptionService = subscriptionService

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}')
    async def unsubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], relay: str, authPermission=Depends(get_auth_permission)):
        if relay == None:
            ...
        if relay != 'sms' and relay != 'email':
            ...

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def resubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], relay: str = Query(), reason:str = Query(), authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/content-subscribe/{contact_id}',[HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def content_subscribe(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        ...
    
    @BaseHTTPRessource.Delete('/content-unsubscribe/{contact_id}')
    async def content_unsubscribe(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PUT])
    async def update_content_subscription_status(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Get('/{contact_id}')
    async def get_contact_subscription(contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        ...


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

    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PUT])
    async def update_raw_contact_security(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        # BUG cant update without having in set up before
        ...

    @UsePermission(JWTContactPermission)
    @UseGuard(RegisteredContactsGuard)
    @PingService([CeleryService,VoiceService,EmailSenderService])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.POST])
    async def create_contact_security(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Query(None), contactPermission=Depends(get_contact_permission), authPermission=Depends(get_auth_permission)):
        # TODO update token permission after use
        ...
    
    @UsePermission(JWTContactPermission)
    @UseGuard(RegisteredContactsGuard)
    @PingService([CeleryService,VoiceService,EmailSenderService])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PATCH])
    async def update_contact_security(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Query(None),forgot:bool=Query(False), contactPermission=Depends(get_contact_permission),  authPermission=Depends(get_auth_permission)):
        # TODO update token permission after use
        ...


@UseHandler(ContactsHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@PingService([ContactsService])
@HTTPRessource(CONTACTS_PREFIX,router= [ContactSecurityRessource,ContactsSubscriptionRessource])
class ContactsRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, contactsService: ContactsService, celeryService: CeleryService, bkgTaskService: BackgroundTaskService,emailService:EmailSenderService,smsService:SMSService):
        super().__init__()
        self.contactsService = contactsService
        self.celeryService = celeryService
        self.bkgTaskService = bkgTaskService
        self.emailService = emailService
        self.smsService = smsService
        self.from_ = Get(ConfigService).getenv('TWILIO_OTP_NUMBER')

    @UsePipe(RelayPipe)
    @UseHandler(TemplateHandler)
    @BaseHTTPRessource.Post('/{relay}')
    async def create_contact(self, relay: str, contact:ContactModel,authPermission=Depends(get_auth_permission)):
        
        #NOTE  if app registered send a jwt token for changing is security shit
        #NOTE double opt in is only to send other than notification like newsletter and promotion anything marketing
        result = await self.contactsService.create_new_contact(contact)
        if contact.info.app_registered:
            return result
        
        return result
        #TODO send welcome email or sms
        template:Template = getattr(self.assetService,relay)[...]
        _,data= template.build(...,{})

        if relay =="sms":
            message = {'body':data,'to':contact.info.phone,'from_':self.from_}
            celeryTask = CeleryTask(task_name='task_send_template_sms',task_type='now',heaviness=TaskHeaviness.VERY_LIGHT,args=(message))
            celery_result = self.celeryService.trigger_task_from_task(celeryTask,None)

        elif relay =="html":
            meta={
                'From':'Contact Management',
                'To':contact.info.email,
                'Subject':'Welcome to our Circle!',
            }
            celeryTask = CeleryTask(task_name='task_send_template_mail',task_type='now',heaviness=TaskHeaviness.LIGHT,args=(data,meta,template.images))
            celery_result = self.celeryService.trigger_task_from_task(celeryTask,None)
        
        return {'result':result,
                'task':celery_result}

    @BaseHTTPRessource.Post('/activate/{contact_id}')
    async def activate_contact(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
        # TODO newsletter and spam like can be sent
        ...

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

    
    async def import_contacts(self):
        ...

    async def export_contacts(self):
        ...