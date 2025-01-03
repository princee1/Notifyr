from typing import Any, Callable, List, Literal, Optional
from services.assets_service import AssetService
from classes.template import HTMLTemplate, TemplateNotFoundError
from classes.email import EmailBuilder
from services.config_service import ConfigService
from services.security_service import SecurityService
from container import InjectInMethod
from definition._ressource import Permission, Ressource, Handler
from definition._service import ServiceNotAvailableError
from services.email_service import EmailSenderService
from pydantic import BaseModel, RootModel
from fastapi import Request, Response, HTTPException, status
from utils.dependencies import get_api_key, get_client_ip, Depends, get_bearer_token


def handling_error(callback: Callable, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except TemplateNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND,)

    except ServiceNotAvailableError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)


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
    attachment: Optional[dict[str, Any]] = {}


class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    content: str
    attachments: Optional[List[tuple[str, str]]] = []
    images: Optional[List[tuple[str, str]]] = []


EMAIL_PREFIX = "email"



class EmailTemplateRessource(Ressource):
    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService):
        super().__init__(EMAIL_PREFIX)
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService

    def on_startup(self):
        super().on_startup()

    def on_shutdown(self):
        super().on_shutdown()

    @Permission()
    @Handler(handling_error)
    def _api_send_emailTemplate(self, template: str, email: EmailTemplateModel,token_= Depends(get_bearer_token), client_ip_=Depends(get_client_ip) ):
        meta = email.meta
        data = email.data
        if template not in self.assetService.htmls:
            raise TemplateNotFoundError

        template: HTMLTemplate = self.assetService.htmls[template]

        flag, data = template.build(data)
        if not flag:

            return
        images = template.images
        self.emailService.send_message(EmailBuilder(data, meta, images))
        pass

    @Permission()
    @Handler(handler_function=handling_error)
    def _api_send_customEmail(self, customEmail: CustomEmailModel, token_= Depends(get_bearer_token), client_ip_=Depends(get_client_ip)):
        meta = customEmail.meta
        content = customEmail.content
        attachment = customEmail.attachments
        images = customEmail.images
        self.emailService.send_message(EmailBuilder(
            attachment, images, content, meta))
        pass

    def _add_routes(self):
        self.router.add_api_route(
            "/template/{template}", self._api_send_emailTemplate, methods=['POST'], description=self._api_send_emailTemplate.__doc__)
        self.router.add_api_route(
            "/custom/", self._api_send_customEmail, methods=['POST'], description=self._api_send_customEmail.__doc__)
