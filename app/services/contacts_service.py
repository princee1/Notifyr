from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi.responses import JSONResponse
from app.classes.auth_permission import ContactPermissionScope
from app.definition._service import BaseService, BuildFailureError, Service, ServiceStatus
from app.errors.contact_error import ContactAlreadyExistsError, ContactDoubleOptInAlreadySetError, ContactOptInCodeNotMatchError
from app.models.contacts_model import *
from app.services.config_service import ConfigService
from app.services.database_service import TortoiseConnectionService
from app.services.link_service import LinkService
from app.services.security_service import JWTAuthService, SecurityService
from random import randint

from app.utils.helper import generateId, b64_encode


MIN_OPT_IN_CODE = 100000000
MAX_OPT_IN_CODE = 999999999


@Service
class SubscriptionService(BaseService):


    def __init__(self,tortoiseConnService:TortoiseConnectionService):
        super().__init__()    
        self.tortoiseConnService= tortoiseConnService

    def build(self):
        ...
    
    def verify_dependency(self):
        if self.tortoiseConnService.service_status != ServiceStatus.AVAILABLE:
            raise BuildFailureError

    async def get_contact_subscription(self, contact: ContactORM, content: ContentSubscriptionORM):
        subs = await SubscriptionORM.filter(contact=contact, content=content).first()
        if subs is None:
            return JSONResponse(content={"detail": "Subscription not found"}, status_code=404)
        return subs

    async def subscribe_user(self, contact: ContactORM, content: ContentSubscriptionORM, relay: str):
        subscription = await SubscriptionORM.create(contact=contact, content=content, preferred_method=relay)
        return JSONResponse(content={"detail": "Subscription created", "subscription": subscription}, status_code=201)

    async def unsubscribe_user(self, contact: ContactORM, content: ContentSubscriptionORM):
        subs = await SubscriptionORM.filter(contact=contact, content=content).first()
        if subs is None:
            return JSONResponse(content={"detail": "Subscription not found"}, status_code=404)
        await subs.delete()
        return JSONResponse(content={"detail": "Subscription deleted"}, status_code=200)

    async def update_subscription(self, contact: ContactORM, content: ContentSubscriptionORM, relay: str, next_status: SubscriptionStatus):
        subs = await SubscriptionORM.filter(contact=contact, content=content).first()
        if subs is None:
            return JSONResponse(content={"detail": "Subscription not found"}, status_code=404)
        subs.preferred_method = relay
        subs.subs_status = next_status
        await subs.save()
        return JSONResponse(content={"detail": "Subscription updated", "subscription": subs}, status_code=200)


@Service
class ContactsService(BaseService):

    def __init__(self, securityService: SecurityService, configService: ConfigService, jwtService: JWTAuthService,linkService:LinkService):
        super().__init__()
        self.securityService = securityService
        self.configService = configService
        self.jwtService = jwtService
        self.linkService = linkService

        self.expiration = 3600000000

    def build(self):
        ...

    @property
    def opt_in_code(self):
        return randint(MIN_OPT_IN_CODE, MAX_OPT_IN_CODE)

    async def toggle_content_type_subs_flag(self, contact: ContactORM, ctype: ContentTypeSubsModel):
        flag: dict = ctype.model_dump(exclude_none=True)
        record: ContentTypeSubscriptionORM = await ContentTypeSubscriptionORM.filter(contact=contact).first()

        for key, item in flag.items():
            setattr(record, key, item)

        await record.save()

    async def unsubscribe_contact(self, contact: ContactORM, next_status: Status):

        contact.status = next_status

        result = {
            'new_status': next_status,
        }

        # NOTE what to do when Blacklist ?
        if next_status == Status.Pending:
            new_opt_in_code = self.opt_in_code
            contact.opt_in_code = new_opt_in_code

            subs = await SubscriptionContactStatusORM.filter(contact=contact).first()
            await subs.delete()

            content = await ContentTypeSubscriptionORM.filter(contact=contact).first()
            await content.delete()

            row_affected = await delete_subscriptions_by_contact(contact.contact_id)

            contact.action_code = None
            result.update({
                'opt_in_code': new_opt_in_code,
            })

        await contact.save()
        result.update(
            {
                'subscriptions_deleted': row_affected
            }
        )
        return result

    async def activate_contact(self, contact: ContactORM, opt_in_code: int, subscription_status: SubscriptionStatusModel):

        if contact.opt_in_code == None:
            raise ContactDoubleOptInAlreadySetError

        if contact.opt_in_code != opt_in_code:
            raise ContactOptInCodeNotMatchError

        subs = subscription_status.model_dump()
        subs.update({'contact': contact})
        subs = await SubscriptionContactStatusORM.create(**subs)

        action_code = generateId(16)

        contact.status = Status.Active.value
        contact.action_code = b64_encode(action_code)
        
        await ContentTypeSubscriptionORM.create(contact=contact)
        await contact.save(force_update=True)
        return action_code

    async def create_new_contact(self, contact: ContactModel):
        email = contact.email
        phone = contact.phone
        user_by_email = None
        user_by_phone = None

        if email != None:
            user_by_email = await ContactORM.filter(email=email).exists()
        if phone != None:
            user_by_phone = await ContactORM.filter(phone=phone).exists()

        if user_by_phone or user_by_email:
            raise ContactAlreadyExistsError(user_by_email, user_by_phone)

        contact_info = contact.model_dump()
        contact_info['opt_in_code'] = self.opt_in_code

        user = await ContactORM.create(**contact_info)
        if user.app_registered:
            user.auth_token = self.jwtService.encode_contact_token(
                str(user.contact_id), self.expiration, 'create')
            

        await user.save()
        # if user.app_registered:
        #     d = user.to_json.copy()
        #     d.update({'auth_token': user.auth_token})
        #     return d
        return user

    async def setup_security(self, contact: ContactORM):

        ...

    async def update_security(self, contact: ContactORM, scope: ContactPermissionScope):
        auth_token = self.jwtService.encode_contact_token(contact.contact_id, self.expiration, scope)
        contact.auth_token = auth_token
        await contact.save(force_update=True)
        return auth_token

    async def update_contact(self,update:UpdateContactModel, contact:ContactORM):
        
        update:dict = update.model_dump()
        for key, value in update.items():
            if value != None:
                setattr(contact, key, value)
        await contact.save()
        return update


    async def read_contact(self, contact_id: str):
        contact = await get_contact_summary(contact_id)
        if contact != None:
            for keys,item in contact.items():
                if isinstance(item,UUID):
                    contact[keys] = str(item)
                    continue
                
                if isinstance(item,datetime):
                    contact[keys] = item.isoformat()
                
        return contact

        user = await ContactORM.filter(contact_id=contact_id).first()
        subs = await SubscriptionContactStatusORM.filter(contact_id=contact_id).first()

        return {'contact_id': contact_id,
                'app_registered': user.app_registered,
                'created-at': user.created_at,
                'updated-at': user.updated_at,
                'email-status': subs.email_status,
                'phone-status': subs.sms_status,
                'subs-updated-at': subs.updated_at,
                'phone': user.phone,
                'email': user.email,
                'lang': user.lang}

    async def filter_registered_contacts(self, by: Literal['email', 'id', 'phone'], app_registered: bool,):

        ...
