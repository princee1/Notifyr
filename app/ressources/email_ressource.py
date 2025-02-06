from typing import Any, Callable, List, Literal, Optional
from app.classes.auth_permission import Role
from app.classes.template import HTMLTemplate, TemplateNotFoundError
from app.definition._service import ServiceStatus
from app.services.celery_service import CeleryService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.container import Get, InjectInMethod
from app.definition._ressource import HTTPRessource, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UsePipe, UseRoles
from app.services.email_service import EmailSenderService
from pydantic import BaseModel
from fastapi import BackgroundTasks, status
from app.utils.dependencies import Depends, get_auth_permission
from app.decorators import permissions, handlers,pipes
from app.classes.celery import  CeleryTask, SchedulerModel


    
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

class EmailTemplateSchedulerModel(SchedulerModel):
    content: EmailTemplateModel

class CustomEmailSchedulerModel(SchedulerModel):
    content: CustomEmailModel


EMAIL_PREFIX = "email"

BASE_SUCCESS_RESPONSE = RessourceResponse(message='email task received successfully')

DEFAULT_RESPONSE = {
    status.HTTP_202_ACCEPTED: {
        'message': 'email task received successfully'}
}



@UseRoles([Role.CHAT,Role.RELAY])
@UseHandler(handlers.ServiceAvailabilityHandler,handlers.CeleryTaskHandler)
@UsePermission(permissions.JWTRouteHTTPPermission)
@UsePipe(pipes.CeleryTaskPipe)
@HTTPRessource(EMAIL_PREFIX)
class EmailTemplateRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService,celeryService:CeleryService):
        super().__init__()
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService
        self.celeryService:CeleryService = celeryService

    @UseRoles([Role.MFA_OTP])
    @UsePermission(permissions.JWTAssetPermission)
    @UseHandler(handlers.TemplateHandler)
    @BaseHTTPRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE)
    def send_emailTemplate(self, template: str, scheduler: EmailTemplateSchedulerModel, background_tasks: BackgroundTasks, authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()
        mail_content = scheduler.content
        if template not in self.assetService.htmls:
            raise TemplateNotFoundError
        
        template: HTMLTemplate = self.assetService.htmls[template]
        _,data = template.build(mail_content.data)
    
        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            if scheduler.task_type == 'now' or scheduler.task_type == 'once':
                background_tasks.add_task( self.emailService.sendTemplateEmail, data, mail_content.meta, template.images )

                return BASE_SUCCESS_RESPONSE
            self.celeryService.pingService()
            return  #TODO  if celery service status is either 4 or 5 
        
        scheduler = scheduler.model_copy(update={'args':(data, mail_content.meta, template.images)})
        model = scheduler.model_dump(mode='python',exclude={'content'})
        return self.celeryService.trigger_task(CeleryTask(**model),scheduler.schedule_name)
        
    @BaseHTTPRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE)
    def send_customEmail(self, scheduler: CustomEmailSchedulerModel, background_tasks: BackgroundTasks, authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()
        customEmail_content = scheduler.content
        content = (customEmail_content.html_content, customEmail_content.text_content)

        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            if scheduler.task_type == 'now' or scheduler.task_type == 'once':
                background_tasks.add_task(self.emailService.sendCustomEmail, content,customEmail_content.meta,customEmail_content.images, customEmail_content.attachments)
                return BASE_SUCCESS_RESPONSE

            self.celeryService.pingService()
            return #TODO  if celery service status is either 4 or 5 
        
        scheduler = scheduler.model_copy(update={'args':( content,customEmail_content.meta,customEmail_content.images, customEmail_content.attachments)})
        model = scheduler.model_dump(mode='python',exclude={'content'})

        return self.celeryService.trigger_task(CeleryTask(**model),scheduler.schedule_name)
