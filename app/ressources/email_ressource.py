from typing import Any, Callable, List, Literal, Optional
from app.services.assets_service import AssetService
from classes.template import HTMLTemplate
from classes.email import EmailBuilder
from services.config_service import ConfigService
from services.security_service import SecurityService
from container import InjectInMethod
from definition._ressource import AssetRessource, Handler
from services.email_service import EmailSenderService
from pydantic import BaseModel, RootModel
from fastapi import Request, Response


def handling_error(callback: Callable, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except:
        pass
    pass


def guard_function(request: Request, **kwargs):

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


class EmailTemplateModel(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]
    attachment: Optional[dict[str, Any]]


class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    content: str
    attachments: Optional[List[tuple[str, str]]]
    images: Optional[List[tuple[str, str]]]


PREFIX = "email"


class EmailTemplateRessource(AssetRessource):
    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService):
        super().__init__(PREFIX)
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService


    def on_startup(self):
        super().on_startup()

    def on_shutdown(self):
        super().on_shutdown()

    @Handler(handler_function=handling_error)
    def send_emailTemplate(self, template_name: str, email: EmailTemplateModel):
        meta = email.meta
        data = email.data
        template:HTMLTemplate = self.assetService.htmls[template_name]
        flag,data = template.build()
        if not flag:
            # raise ValidationError
            return 
        images = template.images
        message = EmailBuilder(data,meta,images)
        self.emailService.send_message(message)
        pass

    @Handler(handler_function=handling_error)
    def send_customEmail(self, customEmail: CustomEmailModel):
        meta = customEmail.meta
        content = customEmail.content
        attachment = customEmail.attachments
        images = customEmail.images
        mess_id,message = EmailBuilder(attachment,images,content,meta).mail_message
        
        pass

    def _add_routes(self):
        self.router.add_api_route(
            "/template/{template_name}", self.send_emailTemplate, methods=['POST'])
        self.router.add_api_route(
            "/custom/", self.send_emailTemplate, methods=['POST'])
