from app.definition._service import Service, ServiceClass

@ServiceClass
class ContactsService(Service):
    
    def build(self):
        ...