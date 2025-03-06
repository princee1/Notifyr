

from typing import Annotated
from fastapi import Depends, HTTPException, Query, status
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseGuard, UsePermission, UsePipe, UseRoles
from app.models.contacts_model import ContactModelORM,ContactModel
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.contacts_service import ContactsService
from app.utils.dependencies import get_auth_permission
from app.decorators.pipes import ContactsIdPipe, RelayPipe
from pydantic import BaseModel


CONTACTS_PREFIX = 'contacts'


async def get_contacts(contact_id: str, idtype: str = Query("id")) -> ContactModelORM:
    match idtype:
        case "id":
            user = await ContactModelORM.filter(contact_id=contact_id)[0]

        case "phone":
            user = await ContactModelORM.filter(phone=contact_id)[0]

        case "email":
            user = await ContactModelORM.filter(email=contact_id)[0]

        case _:
            raise HTTPException(
                400, {"detail": {"message": "idtype not not properly specified"}})

    if user == None:
        raise HTTPException(404, {"detail": "user does not exists"})

    return user


@UseRoles([Role.CONTACTS])
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(CONTACTS_PREFIX)
class ContactsRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, contactsService: ContactsService, celeryService: CeleryService, bkgTaskService: BackgroundTaskService):
        super().__init__()
        self.contactsService = contactsService
        self.celeryService = celeryService
        self.bkgTaskService = bkgTaskService

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.Post('/{relay}')
    async def create_contact(self, relay: str, contact:ContactModel,authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Get('/{contact_id}')
    async def read_contact(self, contact: Annotated[ContactModelORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.HTTPRoute('/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT])
    async def update_contact(self, contact: Annotated[ContactModelORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @BaseHTTPRessource.Delete('/{contact_id}')
    async def delete_contact(self, contact: Annotated[ContactModelORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.TWILIO])
    @BaseHTTPRessource.Post('/security/{contact_id}')
    async def update_contact_security(self, contact: Annotated[ContactModelORM, Depends(get_contacts)], authPermission=Depends(get_auth_permission)):
        ...

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.Delete('/unsubscribe/{contact_id}')
    async def unsubscribe_contact(self, contact: Annotated[ContactModelORM, Depends(get_contacts)], relay: str = Query(), authPermission=Depends(get_auth_permission)):
        if relay == None:
            ...
        if relay != 'sms' and relay != 'email':
            ...

    @UsePipe(RelayPipe)
    @BaseHTTPRessource.HTTPRoute('/resubscribe/{contact_id}', [HTTPMethod.PATCH, HTTPMethod.PUT, HTTPMethod.POST])
    async def resubscribe_contact(self, contact: Annotated[ContactModelORM, Depends(get_contacts)], relay: str = Query(), authPermission=Depends(get_auth_permission)):
        ...
