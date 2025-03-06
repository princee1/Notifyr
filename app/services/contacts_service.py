from app.definition._service import Service, ServiceClass
from app.models.contacts_model import ContactAlreadyExistsError, ContactModel, ContactORM,SubscriptionORM,SecurityContactORM

@ServiceClass
class ContactsService(Service):
    
    def build(self):
        ...
    

    async def create_new_contact(self,contact:ContactModel):
        email = contact.info.email
        phone = contact.info.phone
        user_by_email= None
        user_by_phone =None

        if email != None:
            user_by_email = await ContactORM.filter(email=email)
        if phone !=None:
            user_by_phone = await ContactORM.filter(phone=phone)
        
        if user_by_phone != None or user_by_email!=None:
            raise ContactAlreadyExistsError
        

        user=await ContactORM.create(**contact.info.model_dump())
        contact_id = user.contact_id

        security = contact.security.model_dump()
        security.update({'contact_id':contact_id})
        subs = contact.subscription.model_dump()
        subs.update({'contact_id':contact_id})

        security = await SecurityContactORM.create(**security)
        subs = await SubscriptionORM.create(**subs)
        
    async def update_contact(self,):
        ...    
