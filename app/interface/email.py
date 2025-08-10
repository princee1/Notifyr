from app.definition._interface import Interface, IsInterface

@IsInterface
class EmailSendInterface(Interface):
    def sendTemplateEmail(self, data, meta, images,contact_id=None):
        ...

    def sendCustomEmail(self, content, meta, images, attachment,contact_id=None):
        ...

    def reply_to_an_email(self, content, meta, images, attachment, reply_to, references, contact_ids:list[str]=None):
       ...

    def verify_same_domain_email(self, email: str):
       ...

@IsInterface
class EmailReadInterface(Interface):
    
    def start_jobs():
        ...
    
    def cancel_jobs():
        ...