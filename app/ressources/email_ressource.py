from typing import Any, Callable, List, Literal, Optional
from classes.template import HTMLTemplate, TemplateNotFoundError
from services.config_service import ConfigService
from services.security_service import SecurityService
from container import InjectInMethod
from definition._ressource import Ressource, UsePermission, BaseRessource, UseHandler, NextHandlerException, RessourceResponse
from services.email_service import EmailSenderService
from pydantic import BaseModel, RootModel
from fastapi import BackgroundTasks, Request, Response, HTTPException, status
from utils.dependencies import Depends, get_auth_permission
from decorators import permissions, handlers


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
    attachments: Optional[dict[str, Any]] = {}


class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    text_content: str
    html_content: str
    attachments: Optional[List[tuple[str, str]]] = []
    images: Optional[List[tuple[str, str]]] = []


EMAIL_PREFIX = "email"

BASE_SUCCESS_RESPONSE = RessourceResponse(
    message='email task received successfully')

DEFAULT_RESPONSE = {
    status.HTTP_202_ACCEPTED: {
        'message': 'email task received successfully'}
}

@Ressource(EMAIL_PREFIX)
@UseHandler(handlers.ServiceAvailabilityHandler, start_with='_api_')
class EmailTemplateRessource(BaseRessource):
    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService):
        super().__init__()
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService

    @UsePermission(permissions.JWTRoutePermission, permissions.JWTParamsAssetPermission)
    @UseHandler(handlers.TemplateHandler)
    @BaseRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE)
    def _api_send_emailTemplate(self, template: str, email: EmailTemplateModel, background_tasks: BackgroundTasks, authPermission=Depends(get_auth_permission)):
        
        self.emailService.pingService()

        meta = email.meta
        data = email.data
        if template not in self.assetService.htmls:
            raise TemplateNotFoundError

        template: HTMLTemplate = self.assetService.htmls[template]

        flag, data = template.build(data)
        if not flag:
            return HTTPException(status.HTTP_400_BAD_REQUEST, detail={'description': data, 'message': 'Validation Error'})
        images = template.images
        background_tasks.add_task(
            self.emailService.sendTemplateEmail, data, meta, images)

        return BASE_SUCCESS_RESPONSE

    @UsePermission(permissions.JWTRoutePermission)
    @BaseRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE)
    def _api_send_customEmail(self, customEmail: CustomEmailModel, background_tasks: BackgroundTasks, authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()
        
        meta = customEmail.meta
        text_content = customEmail.text_content
        html_content = customEmail.html_content
        content = (html_content, text_content)
        attachment = customEmail.attachments
        images = customEmail.images

        background_tasks.add_task(
            self.emailService.sendCustomEmail, content, meta, images, attachment)

        return BASE_SUCCESS_RESPONSE


    def _api_schedule_custom_email(self, customEmail:CustomEmailModel, authPermission=Depends(get_auth_permission)):
        ...

    def _api_schedule_template(self, template:str, email: EmailTemplateModel, authPermission=Depends(get_auth_permission)):
        ...
