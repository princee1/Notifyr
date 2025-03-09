

from typing import Annotated
from fastapi import Depends, HTTPException, Query, status
from app.classes.auth_permission import Role
from app.classes.celery import CeleryTask, TaskHeaviness
from app.classes.template import Template
from app.container import Get, InjectInMethod
from app.decorators.handlers import ContactsHandler, TemplateHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UseHandler, UsePermission, UsePipe, UseRoles
from app.models.contacts_model import ContactORM,ContactModel
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.email_service import EmailSenderService
from app.services.twilio_service import SMSService
from app.utils.dependencies import get_auth_permission
from app.decorators.pipes import ContactsIdPipe, RelayPipe
from pydantic import BaseModel


CONTACTS_PREFIX = 'contacts'


async def get_contacts(contact_id: str, idtype: str = Query("id")) -> ContactORM:
    match idtype:
        case "id":
            user = await ContactORM.filter(contact_id=contact_id)[0]

        case "phone":
            user = await ContactORM.filter(phone=contact_id)[0]

        case "email":
            user = await ContactORM.filter(email=contact_id)[0]

        case _:
            raise HTTPException(
                400, {"detail": {"message": "idtype not not properly specified"}})

    if user == None:
        raise HTTPException(404, {"detail": "user does not exists"})

    return user


@UseHandler(ContactsHandler)
@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CONTACTS_PREFIX)
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
        
        result = await self.contactsService.create_new_contact(contact)
        if contact.info.app_registered:
            return result
        

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Get('/{contact_id}')
    async def read_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        return await self.contactsService.read_contact(contact.contact_id)

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT])
    async def update_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Delete('/{contact_id}')
    async def delete_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Post('/security/{contact_id}')
    async def update_contact_security(self, contact: Annotated[ContactORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}')
    async def unsubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], relay: str = Query(), authPermission=Depends(get_auth_permission)):
        if relay == None:
            ...
        if relay != 'sms' and relay != 'email':
            ...

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def resubscribe_contact(self, contact: Annotated[ContactORM, Depends(get_contacts)], relay: str = Query(), authPermission=Depends(get_auth_permission)):
        ...
