

from typing import Annotated
from fastapi import Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from app.classes.auth_permission import MustHave, MustHaveRoleSuchAs, Role
from app.container import Get,InjectInMethod
from app.decorators.guards import ActiveContactGuard, ContactActionCodeGuard, RegisteredContactsGuard
from app.decorators.handlers import AsyncIOHandler, ContactsHandler, TemplateHandler, TortoiseHandler, handle_http_exception
from app.depends.funcs_dep import get_contact_permission, Get_Contact, get_subs_content,verify_twilio_token
from app.decorators.permissions import JWTContactPermission, JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseServiceLock, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.depends.orm_cache import ContactORMCache,ContactSummaryORMCache
from app.models.contacts_model import AppRegisteredContactModel, ContactORM,ContactModel, ContentSubscriptionModel, ContentTypeSubsModel, Status, ContentSubscriptionORM, SubscriptionORM, SubscriptionStatus, UpdateContactModel, get_all_contact_summary, get_contact_summary
from app.services.task_service import TaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.contacts_service import MAX_OPT_IN_CODE, MIN_OPT_IN_CODE, ContactsService, SubscriptionService
from app.services.database_service import TortoiseConnectionService
from app.services.email_service import EmailSenderService
from app.services.security_service import JWTAuthService, SecurityService
from app.services.twilio_service import SMSService, CallService
from app.depends.dependencies import get_auth_permission, get_contact_token
from app.decorators.pipes import ContactStatusPipe, RelayPipe
from app.depends.variables import summary_query


CONTACTS_PREFIX = 'contacts'
CONTACTS_SECURITY_PREFIX = 'security'
CONTACTS_SUBSCRIPTION_PREFIX = 'subscribe'
SUBSCRIPTION_PREFIX = 'subscription'
CONTACTS_CRUD_PREFIX = 'manage'

get_contacts = Get_Contact(False,False)
       
##############################################                   ##################################################

@PingService([TortoiseConnectionService])
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@UseHandler(TortoiseHandler,AsyncIOHandler)
@UsePermission(JWTRouteHTTPPermission)
@UseRoles([Role.SUBSCRIPTION])
@HTTPRessource(SUBSCRIPTION_PREFIX)
class ContentSubscriptionRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,contactsService:ContactsService,subscriptionService:SubscriptionService):
        super().__init__()
        self.contactsService = contactsService
        self.subscriptionService = subscriptionService
    
    @BaseHTTPRessource.Post('/')
    async def register_content_subscription(self, contentSubsModel: ContentSubscriptionModel, authPermission=Depends(get_auth_permission)):
        if not all([contentSubsModel.content_name, contentSubsModel.content_type, contentSubsModel.content_description]):
            return JSONResponse(content={"detail": "Missing required fields"}, status_code=status.HTTP_400_BAD_REQUEST)
        
        content = await ContentSubscriptionORM.create(**contentSubsModel.model_dump())
        return JSONResponse(content={"detail": "Subscription registered", "content": content}, status_code=status.HTTP_201_CREATED)

    @BaseHTTPRessource.Delete('/')
    async def delete_content_subscription(self, subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], authPermission=Depends(get_auth_permission)):
        await subs_content.delete()
        return JSONResponse(content={"detail": "Subscription deleted"}, status_code=status.HTTP_200_OK)

    @BaseHTTPRessource.Get('/')
    async def get_content_subscription(self, subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], authPermission=Depends(get_auth_permission)):
        return JSONResponse(content={"detail": "Subscription retrieved", "content": subs_content}, status_code=status.HTTP_200_OK)

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def update_subscription(self, contentSubsModel: ContentSubscriptionModel, subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], authPermission=Depends(get_auth_permission)):
        if contentSubsModel.content_name:
            subs_content.content_name = contentSubsModel.content_name
        if contentSubsModel.content_description:
            subs_content.content_description = contentSubsModel.content_description
        if contentSubsModel.content_ttl:
            subs_content.content_ttl = contentSubsModel.content_ttl
        if contentSubsModel.content_type:
            subs_content.content_type = contentSubsModel.content_type

        await subs_content.save()
        return JSONResponse(content={"detail": "Subscription updated", "content": subs_content}, status_code=status.HTTP_200_OK)

##############################################                   ##################################################
@UseHandler(TortoiseHandler, ContactsHandler,AsyncIOHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@PingService([ContactsService,TortoiseConnectionService])
@HTTPRessource(CONTACTS_SUBSCRIPTION_PREFIX)
class ContactsSubscriptionRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self, contactService: ContactsService, subscriptionService: SubscriptionService):
        super().__init__()
        self.contactService = contactService
        self.subscriptionService = subscriptionService

    @UseRoles([Role.RELAY])
    @UseGuard(ContactActionCodeGuard)
    @UseGuard(ActiveContactGuard)
    @UseHandler(TemplateHandler)
    @UsePipe(ContactStatusPipe)
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}/')
    async def unsubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], action_code=Query(None), next_status: Status = Query(None), authPermission=Depends(get_auth_permission)):
        if next_status == Status.Active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Next status cannot be set to Active when unsubscribing the contact")
        
        contact_id = str(contact.contact_id)
        result = await self.contactService.unsubscribe_contact(contact, next_status)
        await ContactORMCache.Store(contact_id,contact)
        await ContactSummaryORMCache.Store(contact_id,contact_id=contact_id)

        return JSONResponse(content=result, status_code=status.HTTP_200_OK)

    @UseGuard(ContactActionCodeGuard)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}/', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def resubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], action_code: str = Query(None), authPermission=Depends(get_auth_permission)):
        if contact.status == Status.Active:
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"detail": "Nothing to do"})
        contact_id = str(contact.contact_id)
        
        if contact.status in [Status.Inactive, Status.Blacklist]:
            contact.status = Status.Active
            await contact.save()
            await ContactORMCache.Store(str(contact.contact_id),contact)
            await ContactSummaryORMCache.Store(contact_id,contact_id=contact_id)

            return JSONResponse(content={"detail": "Reactivated the contact back to active"}, status_code=status.HTTP_200_OK)
        
        return JSONResponse(content={"detail": "You must reactivate your account with your new opt-in code"}, status_code=status.HTTP_423_LOCKED)

    @UsePipe(RelayPipe(False))
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-subscribe/{contact_id}/', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def content_subscribe(self, contact: Annotated[ContactORM, Depends(get_contacts)], subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], relay: str = Query(None), authPermission=Depends(get_auth_permission)):
        response = await self.subscriptionService.subscribe_user(contact, subs_content, relay)
        return response

    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.HTTPRoute('/content-preferences/{contact_id}/', [HTTPMethod.POST])
    async def toggle_content_type_preferences(self, flags_content_types: ContentTypeSubsModel, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        await self.contactService.toggle_content_type_subs_flag(contact, flags_content_types)
        return JSONResponse(content={"detail": "Content type preferences updated"}, status_code=status.HTTP_200_OK)

    @UseGuard(ContactActionCodeGuard(True))  # NOTE the server can bypass the action_code guard only if the subs_content is notification or update
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.Delete('/content-unsubscribe/{contact_id}')
    async def content_unsubscribe(self, contact: Annotated[ContactORM, Depends(get_contacts)], subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], action_code: str = Query(None), authPermission=Depends(get_auth_permission)):
        return await self.subscriptionService.unsubscribe_user(contact, subs_content)     

    @UseGuard(ContactActionCodeGuard(True))  # NOTE the server can bypass the action_code guard only if the subs_content is notification or update
    @UseGuard(ActiveContactGuard)
    @UsePipe(RelayPipe)
    @BaseHTTPRessource.HTTPRoute('/content-status/{contact_id}/', [HTTPMethod.POST])
    async def update_content_subscription(self, contact: Annotated[ContactORM, Depends(get_contacts)], subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], relay: str = Query(None), action_code: str = Query(None), next_subs_status: SubscriptionStatus = Query(None), authPermission=Depends(get_auth_permission)):
        if not next_subs_status:
            return JSONResponse(content={"detail": "Next subscription status is required"}, status_code=status.HTTP_400_BAD_REQUEST)
        
        return await self.subscriptionService.update_subscription(contact, subs_content, relay, next_subs_status)
        
    @UseGuard(ActiveContactGuard)
    @BaseHTTPRessource.Get('/{contact_id}')
    async def get_contact_subscription(self, contact: Annotated[ContactORM, Depends(get_contacts)], subs_content: Annotated[ContentSubscriptionORM, Depends(get_subs_content)], authPermission=Depends(get_auth_permission)):
        return await self.subscriptionService.get_contact_subscription(contact, subs_content)
        

@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@UseHandler(TortoiseHandler,ContactsHandler,AsyncIOHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@PingService([ContactsService,TortoiseConnectionService])
@HTTPRessource(CONTACTS_SECURITY_PREFIX)
class ContactSecurityRessource(BaseHTTPRessource):
    
    @InjectInMethod()
    def __init__(self,securityService:SecurityService,jwtService:JWTAuthService,contactsService:ContactsService,celeryService:CeleryService ):
        super().__init__()
        self.securityService = securityService
        self.jwtAuthService = jwtService
        self.contactService = contactsService
        self.celeryService = celeryService
    
    @UseGuard(RegisteredContactsGuard)
    @UseRoles(roles=[Role.TWILIO],options=[MustHave(Role.TWILIO)])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.GET],dependencies=[Depends(verify_twilio_token)])
    async def check_password(self,contact: Annotated[ContactORM, Depends(get_contacts)],request:Request, authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles(roles=[Role.TWILIO],options=[MustHave(Role.TWILIO)])
    @UsePermission(JWTContactPermission('update'))
    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PUT],dependencies=[Depends(verify_twilio_token)])
    async def update_raw_contact_security(self, contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Depends(get_contact_token),contactPermission=Depends(get_contact_permission), authPermission=Depends(get_auth_permission)):
        # TODO update token permission after use
        ...

    @UsePermission(JWTContactPermission('create'))
    @UseGuard(RegisteredContactsGuard)
    @PingService([CeleryService,CallService,EmailSenderService])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.POST])
    async def request_create_contact_security(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Depends(get_contact_token), contactPermission=Depends(get_contact_permission), authPermission=Depends(get_auth_permission)):
        # TODO Request from the user
        # TODO hash the token before sending
        ...
    
    @UsePermission(JWTContactPermission('update'))
    @UseGuard(RegisteredContactsGuard)
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PATCH])
    async def request_update_contact_security(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Depends(get_contact_token),forgot:bool=Query(False), contactPermission=Depends(get_contact_permission),  authPermission=Depends(get_auth_permission)):
        # TODO request from the user
        # TODO hash the token before sending
        ...

    @UseRoles(roles=[Role.TWILIO],options=[MustHave(Role.TWILIO)])
    @UseGuard(RegisteredContactsGuard)
    @UsePermission(JWTContactPermission('update'))
    @BaseHTTPRessource.HTTPRoute('/token/{contact_id}',[HTTPMethod.GET],dependencies=[Depends(verify_twilio_token)])
    async def verify_token(self,contact: Annotated[ContactORM, Depends(get_contacts)],token:str=Depends(get_contact_token),contactPermission=Depends(get_contact_permission),authPermission=Depends(get_auth_permission)):
        return
    
    # @UseRoles(options=[MustHaveRoleSuchAs(Role.CONTACTS,Role.REFRESH,Role.RELAY)])
    # @UseGuard(RegisteredContactsGuard)
    # @BaseHTTPRessource.HTTPRoute('/token/{contact_id}',[HTTPMethod.POST])
    # async def request_new_token(self,contact: Annotated[ContactORM, Depends(get_contacts)],authPermission=Depends(get_auth_permission)):
    #     ...


#@UseHandler(handle_http_exception)
@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@UseHandler(TortoiseHandler, ContactsHandler,AsyncIOHandler)
@PingService([ContactsService,TortoiseConnectionService])
@HTTPRessource(CONTACTS_CRUD_PREFIX)
class ContactsCRUDRessource(BaseHTTPRessource):
    @InjectInMethod()
    def __init__(self, contactsService: ContactsService, celeryService: CeleryService, bkgTaskService: TaskService, emailService: EmailSenderService, smsService: SMSService):
        super().__init__()
        self.contactsService = contactsService
        self.celeryService = celeryService
        self.bkgTaskService = bkgTaskService

    @UseLimiter(limit_value='2000/minutes')
    @BaseHTTPRessource.Post('/')
    async def create_contact(self, contact: ContactModel,request:Request,response:Response):
        new_contact = await self.contactsService.create_new_contact(contact)
        contact_id = str(new_contact.contact_id)
        
        await ContactORMCache.Store(str(contact_id),new_contact)
        return JSONResponse(content={"detail": "Contact created", "contact": new_contact.to_json}, status_code=status.HTTP_201_CREATED)

    @BaseHTTPRessource.HTTPRoute('/{contact_id}/',methods=[HTTPMethod.PATCH])
    async def activate_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], opt: int = Query(ge=MIN_OPT_IN_CODE, le=MAX_OPT_IN_CODE)):
        action_code = await self.contactsService.activate_contact(contact, opt)
        contact_id = str(contact.contact_id)
        await ContactSummaryORMCache.Store(contact_id,contact_id=contact_id)
        await ContactORMCache.Store(str(contact.contact_id),contact)
        return JSONResponse(content={"detail": "Contact activated", "action_code": action_code}, status_code=status.HTTP_200_OK)

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Get('/{contact_id}/')
    async def read_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)],is_summary:bool=Depends(summary_query)):
        if is_summary:
            contact_data = await self.contactsService.read_contact(contact.contact_id)
        else:
            contact_data = contact.to_json
        return JSONResponse(content={"detail": "Contact retrieved", "contact": contact_data}, status_code=status.HTTP_200_OK)

    @BaseHTTPRessource.HTTPRoute('/{contact_id}/', [HTTPMethod.PATCH, HTTPMethod.PUT])
    async def update_contact(self, update_contact_model: UpdateContactModel, contact: Annotated[ContactORM, Depends(get_contacts)]):
        updated_contact = await self.contactsService.update_contact(update_contact_model, contact)
        contact_id = str(contact.contact_id)
        await ContactSummaryORMCache.Store(contact_id,contact_id=contact_id)
        await ContactORMCache.Store(str(contact.contact_id),contact)
        return JSONResponse(content={"detail": "Contact updated", "contact": updated_contact}, status_code=status.HTTP_200_OK)

    @BaseHTTPRessource.Delete('/{contact_id}/')
    async def delete_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)],is_summary:bool=Depends(summary_query)):
        if is_summary:
            content_data = await self.contactsService.read_contact(contact.contact_id)
        else:
            content_data = contact.to_json

        contact_id = str(contact.contact_id)
        await ContactORMCache.Invalid(contact_id)
        await ContactSummaryORMCache.Invalid(contact_id)
        await contact.delete()
        return JSONResponse(content={"detail": "Contact deleted", "contact":content_data}, status_code=status.HTTP_200_OK)

@UseServiceLock(TortoiseConnectionService,lockType='reader',infinite_wait=True)
@UseHandler(TortoiseHandler, ContactsHandler,AsyncIOHandler)
@UseRoles([Role.CONTACTS])
@PingService([ContactsService,TortoiseConnectionService])
@HTTPRessource(CONTACTS_PREFIX, routers=[ContactsCRUDRessource,ContactSecurityRessource,ContentSubscriptionRessource, ContactsSubscriptionRessource,])
class ContactsRessource(BaseHTTPRessource):

    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/registered/',methods=[HTTPMethod.PUT])
    async def set_app_registered(self, app_registered_model:AppRegisteredContactModel,contact:Annotated[ContactORM,Depends(get_contacts)],response:Response,authPermission=Depends(get_auth_permission)):
        contact.app_registered = app_registered_model.app_registered
        await contact.save(force_update=True)
        
        contact_id = str(contact.contact_id)
        await ContactSummaryORMCache.Store(contact_id,contact_id=contact_id)
        await ContactORMCache.Store(contact_id,contact)

    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/all')
    async def get_all_contacts(self, authPermission=Depends(get_auth_permission)):
        row_affected, result = await get_all_contact_summary()
        return JSONResponse(content={"detail": "All contacts retrieved", "contacts": result}, status_code=status.HTTP_200_OK)
    
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Get('/file',mount=False)
    async def import_contacts(self,authPermission=Depends(get_auth_permission)):
        raise NotImplementedError
    
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.Post('/file',mount=False)
    async def export_contacts(self,authPermission=Depends(get_auth_permission)):
        raise NotImplementedError

##############################################                   ##################################################
