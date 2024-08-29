from typing import Any, Callable, List, Literal, Optional
from services.config_service import ConfigService
from services.security_service import SecurityService
from container import InjectInConstructor
from definition._ressource import AssetRessource, Handler
from services.email_service import EmailSenderService
from pydantic import BaseModel, RootModel


def handling_error(callback: Callable, *args, **kwargs):
    try:
        pass
    except:
        pass
    pass


def guard_function():
    pass


class EmailMetaModel(BaseModel):
    Subject: str
    From: str
    To: str | List[str]
    CC: Optional[str] = None,
    Bcc: Optional[str] = None,
    replyTo: Optional[str] = None,
    Return_Path: Optional[str] = None,
    Priority: Literal['1', '3', '5'] = '1'


class EmailTemplate(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]

class CustomEmail(BaseModel):
    meta: EmailMetaModel
    content: str
    attachements: Optional[List[tuple[str, str]]]
    images: Optional[List[tuple[str, str]]]

PREFIX= "email"


class EmailTemplateRessource(AssetRessource):
    @InjectInConstructor
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService) -> None:
        super().__init__(PREFIX)
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService

        self.router.add_api_route("template",self.send_emailTemplate)
        self.router.add_api_route("custom",self.send_emailTemplate)


    @Handler(handler_function=handling_error)
    def send_emailTemplate(self):
        pass

    @Handler(handler_function=handling_error)
    def send_customEmail(self):
        pass

    def on_startup(self):
        return super().on_startup()

    def on_shutdown(self):
        return super().on_shutdown()
