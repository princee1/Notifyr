from typing import Callable
from app.services.config_service import ConfigService
from container import InjectInConstructor
from definition._ressource import AssetRessource,Handler
from app.services.email_service import EmailSenderService


def handling_error(callback:Callable,*args,**kwargs):
    try:
        pass
    except:
        pass
    pass

def MiddleWare():
    pass

class EmailTemplateRessource(AssetRessource):
    @InjectInConstructor
    def __init__(self, emailSender:EmailSenderService,configService:ConfigService) -> None:
        super().__init__("email-template")
        self.emailService: EmailSenderService = emailSender
        self.configService:ConfigService =  configService
        

    @Handler(handler_function=handling_error)
    def sendEmailTemplate(self):
        pass

    def on_startup(self):
        return super().on_startup()
    
    def on_error(self):
        return super().on_error()
    
    def on_shutdown(self):
        return super().on_shutdown() 

    def on_event(self):
        return super().on_event()
    



    

