from app.definition._service import Service, ServiceClass
from app.models.contacts_model import ContactAlreadyExistsError, ContactModel, ContactORM, SubscriptionORM, SecurityContactORM


@ServiceClass
class ContactsService(Service):

    def build(self):
        ...

    async def create_new_contact(self, contact: ContactModel):
        email = contact.info.email
        phone = contact.info.phone
        user_by_email = None
        user_by_phone = None

        if email != None:
            user_by_email = await ContactORM.filter(email=email) == None
        if phone != None:
            user_by_phone = await ContactORM.filter(phone=phone) == None

        if user_by_phone or user_by_email:
            raise ContactAlreadyExistsError(user_by_email, user_by_phone)

        user = await ContactORM.create(**contact.info.model_dump())
        contact_id = user.contact_id

        security = contact.security.model_dump()
        security.update({'contact_id': contact_id})
        subs = contact.subscription.model_dump()
        subs.update({'contact_id': contact_id})

        security = await SecurityContactORM.create(**security)
        subs = await SubscriptionORM.create(**subs)

        return {'contact_id': contact_id,
                'app_registered': user.app_registered,
                'created-at': user.created_at,
                'updated-at': user.updated_at}

    async def update_contact(self,):
        ...

    async def read_contact(self, contact_id: str):
        user = await ContactORM.filter(contact_id=contact_id)
        user = user[0]
        subs = await SubscriptionORM.filter(contact_id=contact_id)[0]
        subs = subs[0]

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
