from typing import Any, Callable, List, Literal, Optional
from app.classes.auth_permission import Role
from app.classes.template import HTMLTemplate, TemplateNotFoundError
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.container import Get, InjectInMethod
from app.definition._ressource import HTTPRessource, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UseRoles
from app.services.email_service import EmailSenderService
from pydantic import BaseModel, RootModel
from fastapi import BackgroundTasks, Request, Response, HTTPException, status
from app.utils.dependencies import Depends, get_auth_permission
from app.decorators import permissions, handlers

    
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


@UseRoles([Role.CHAT,Role.RELAY])
@HTTPRessource(EMAIL_PREFIX)
@UseHandler(handlers.ServiceAvailabilityHandler)
class EmailTemplateRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService):
        super().__init__()
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService

    @UseRoles([Role.MFA_OTP])
    @UsePermission(permissions.JWTRouteHTTPPermission, permissions.JWTAssetPermission)
    @UseHandler(handlers.TemplateHandler)
    @BaseHTTPRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE)
    def send_emailTemplate(self, template: str, email: EmailTemplateModel, background_tasks: BackgroundTasks, authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()

        if template not in self.assetService.htmls:
            raise TemplateNotFoundError
        template: HTMLTemplate = self.assetService.htmls[template]
        flag, data = template.build(email.data)
        if not flag:
            return HTTPException(status.HTTP_400_BAD_REQUEST, detail={'description': data, 'message': 'Validation Error'})
        background_tasks.add_task( self.emailService.sendTemplateEmail, data, email.meta, template.images)

        return BASE_SUCCESS_RESPONSE

    @UsePermission(permissions.JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE)
    def send_customEmail(self, customEmail: CustomEmailModel, background_tasks: BackgroundTasks, authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()

        content = (customEmail.html_content, customEmail.text_content)
        background_tasks.add_task(self.emailService.sendCustomEmail, content,customEmail.meta,customEmail.images, customEmail.attachments)
        
        return BASE_SUCCESS_RESPONSE

