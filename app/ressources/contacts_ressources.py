

from fastapi import Depends, Query
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UsePermission, UsePipe, UseRoles
from app.models.contacts_model import ContactModel
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.contacts_service import ContactsService
from app.utils.dependencies import get_auth_permission
from app.decorators.pipes import ContactsIdPipe, RelayPipe

CONTACTS_PREFIX = 'contacts'


@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CONTACTS_PREFIX)
class ContactsRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, contactsService: ContactsService,celeryService:CeleryService,bkgTaskService:BackgroundTaskService):
        super().__init__()
        self.contactsService = contactsService
        self.celeryService = celeryService
        self.bkgTaskService = bkgTaskService

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.Post('/{relay}')
    def create_contact(self,relay:str, authPermission=Depends(get_auth_permission)):
        ...
    
    @UseRoles([Role.TWILIO])
    @UsePipe(ContactsIdPipe)
    @BaseHTTPRessource.Get('/{contact_id}')
    def read_contact(self,contact_id:str, authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.TWILIO])
    @UsePipe(ContactsIdPipe)
    @BaseHTTPRessource.HTTPRoute('/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT])
    def update_contact(self, contact_id: str, authPermission=Depends(get_auth_permission)):
        ...

    @UsePipe(ContactsIdPipe)
    @BaseHTTPRessource.Delete('/{contact_id}')
    def delete_contact(self, contact_id: str,authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.TWILIO])
    @UsePipe(ContactsIdPipe)
    @BaseHTTPRessource.Post('/security/{contact_id}')
    def update_contact_security(self, contact_id: str, authPermission=Depends(get_auth_permission)):
        ...

    @UsePipe(RelayPipe)
    @UsePipe(ContactsIdPipe)
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}')
    def unsubscribe_contact(self, contact_id: str, relay:str =Query(),authPermission=Depends(get_auth_permission)):
        if relay == None:
         ...
        if relay != 'sms' and relay != 'email':
            ...

    @UsePipe(RelayPipe)
    @UsePipe(ContactsIdPipe)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    def resubscribe_contact(self, contact_id: str,relay:str =Query(),authPermission=Depends(get_auth_permission)):
        ...
