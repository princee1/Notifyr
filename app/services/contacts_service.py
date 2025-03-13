from datetime import datetime, timezone
from typing import Literal
from app.definition._service import Service, ServiceClass
from app.models.contacts_model import ContactAlreadyExistsError, ContactModel, ContactORM, SubscriptionContactORM, SecurityContactORM
from tortoise.exceptions import OperationalError

from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService, SecurityService


@ServiceClass
class SubscriptionService(Service):
    ...




@ServiceClass
class ContactsService(Service):

    def __init__(self,securityService:SecurityService,configService:ConfigService,jwtService:JWTAuthService):
        super().__init__()
        self.securityService = securityService
        self.configService = configService
        self.jwtService = jwtService

    def build(self):
        ...


    def create_contacts_security_permission(self):
        # TODO Delete after used
        ...
    
    def activate_newsletter_contact(self,): # Only if your are not app registered
        ...

    async def create_new_contact(self, contact: ContactModel):
        email = contact.info.email
        phone = contact.info.phone
        user_by_email = None
        user_by_phone = None

        if email != None:
            user_by_email = await ContactORM.filter(email=email).exists()
        if phone != None:
            user_by_phone = await ContactORM.filter(phone=phone).exists()

        if user_by_phone or user_by_email:
            raise ContactAlreadyExistsError(user_by_email, user_by_phone)

        contact_info = contact.info.model_dump()
        user = await ContactORM.create(**contact_info)

        security = contact.security.model_dump()
        security.update({'contact': user})

        hash_key = self.configService.CONTACTS_HASH_KEY
        security_code = str(security['security_code'])

        if security_code:
            security['security_code'],security['security_code_salt'] = self.securityService.store_password(security_code,hash_key)
            
        security_code_phrase = security['security_phrase']
        if security_code_phrase:
            security['security_phrase'],security['security_phrase_salt'] = self.securityService.store_password(security_code_phrase,hash_key)

        subs = contact.subscription.model_dump()
        subs.update({'contact': user})

        security = await SecurityContactORM.create(**security)
        subs = await SubscriptionContactORM.create(**subs)
        
        return user.to_json

    async def update_contact(self,):
        ...

    async def read_contact(self, contact_id: str):
        user = await ContactORM.filter(contact_id=contact_id).first()
        subs = await SubscriptionContactORM.filter(contact_id=contact_id).first()

        return {'contact_id': contact_id,
                'app_registered': user.app_registered,
                'created-at': user.created_at,
                'updated-at': user.updated_at,
                'email-status': subs.email_status,
                'phone-status': subs.sms_status,
                'subs-updated-at':subs.updated_at,
                'phone': user.phone,
                'email': user.email,
                'lang': user.lang}

    async def filter_registered_contacts(self,by:Literal['email','id','phone'],app_registered:bool,):

        ...