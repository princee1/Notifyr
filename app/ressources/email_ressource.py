from typing import Any, Callable, List, Literal, Optional
from services.assets_service import AssetService
from classes.template import HTMLTemplate, TemplateNotFoundError
from classes.email import EmailBuilder
from services.config_service import ConfigService
from services.security_service import SecurityService
from container import InjectInMethod
from definition._ressource import Ressource, UsePermission, BaseRessource, UseHandler,NextHandlerException
from definition._service import ServiceNotAvailableError
from services.email_service import EmailSenderService
from pydantic import BaseModel, RootModel
from fastapi import Request, Response, HTTPException, status
from utils.dependencies import Depends,get_auth_permission
from decorators import permissions

def handling_error(callback: Callable, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except TemplateNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND,)

    except ServiceNotAvailableError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as e:
        #raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)
        print(e)
        raise NextHandlerException


def guard_function(request: Request, **kwargs):

    pass


class EmailMetaModel(BaseModel):
    Subject: str
    From: str
    To: str | List[str]
    CC: Optional[str] = None
    Bcc: Optional[str] = None
    replyTo: Optional[str] = None
    Return_Path: Optional[str] = None
    Priority: Literal['1', '3', '5'] = '1'


class EmailTemplateModel(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]
    attachment: Optional[dict[str, Any]] = {}


class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    text_content: str
    html_content: str
    attachments: Optional[List[tuple[str, str]]] = []
    images: Optional[List[tuple[str, str]]] = []


EMAIL_PREFIX = "email"

@Ressource(EMAIL_PREFIX)
class EmailTemplateRessource(BaseRessource):
    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService):
        super().__init__()
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService

    def on_startup(self):
        super().on_startup()

    def on_shutdown(self):
        super().on_shutdown()

    @UsePermission(permissions.JWTRoutePermission,permissions.JWTParamsAssetPermission)
    @UseHandler(handling_error)
    @BaseRessource.HTTPRoute("/template/{template}",)
    def _api_send_emailTemplate(self, template: str, email: EmailTemplateModel, authPermission = Depends(get_auth_permission)):

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

    @UsePermission(permissions.JWTRoutePermission)
    @UseHandler(handling_error)
    @BaseRessource.HTTPRoute("/custom/",)
    def _api_send_customEmail(self, customEmail: CustomEmailModel, authPermission = Depends(get_auth_permission)):
        meta = customEmail.meta
        text_content = customEmail.text_content
        html_content = customEmail.html_content
        content = (html_content, text_content)
        attachment = customEmail.attachments
        images = customEmail.images
        self.emailService.send_message(EmailBuilder(content,meta,images,attachment))

    def _add_handcrafted_routes(self):
        # self.router.add_api_route(
        #     "/template/{template}", self._api_send_emailTemplate, methods=["POST"],description=self._api_send_emailTemplate.__doc__)
        # self.router.add_api_route(
        #     "/custom/", self._api_send_customEmail, methods=["POST"],description=self._api_send_customEmail.__doc__)
        ...