from typing import Callable
from services.config_service import ConfigService
from services.security_service import SecurityService
from container import InjectInConstructor
from definition._ressource import AssetRessource,Handler
from services.email_service import EmailSenderService
from pydantic import BaseModel


def handling_error(callback:Callable,*args,**kwargs):
    try:
        pass 
    except:
        pass
    pass

def guard_function():
    pass


class EmailModel(BaseModel):
    pass

class EmailTemplateRessource(AssetRessource):
    @InjectInConstructor
    def __init__(self, emailSender:EmailSenderService,configService:ConfigService,securityService:SecurityService) -> None:
        super().__init__("email-template")
        self.emailService: EmailSenderService = emailSender
        self.configService:ConfigService =  configService
        self.securityService: SecurityService = securityService

    @Handler(handler_function=handling_error)
    def sendEmailTemplate(self):
        pass

    @Handler(handler_function=handling_error) 
    def sendSimpleEmail(self):
        pass

    def on_startup(self):
        return super().on_startup()
    
    def on_error(self):
        return super().on_error()
    
    def on_shutdown(self):
        return super().on_shutdown() 

    def on_event(self):
        return 
