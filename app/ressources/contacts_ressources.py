

from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePermission, UseRoles
from app.services.contacts_service import ContactsService

CONTACTS_PREFIX = 'contacts'

@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CONTACTS_PREFIX)
class ContactsRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,contactsService:ContactsService):
        super().__init__()
        self.contactsService = contactsService

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Get('/{contact_id}')
    def get_contact(self,):
        ...

    @BaseHTTPRessource.Post('/')
    def create_contact(self,):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/{contact_id}',[HTTPMethod.PATCH,HTTPMethod.PUT])
    def update_contact(self,):
        ...

    @BaseHTTPRessource.Delete('/{contact_id}')
    def delete_contact(self,):
        ...
