from typing import Annotated, Any, Callable, List, Literal, Optional
from app.classes.auth_permission import MustHave, Role
from app.classes.template import HTMLTemplate, TemplateNotFoundError
from app.definition._service import ServiceStatus
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.container import GetDepends, InjectInMethod
from app.definition._ressource import HTTPRessource, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UsePipe, UseRoles
from app.services.email_service import EmailSenderService
from pydantic import BaseModel
from fastapi import BackgroundTasks, Header, Request, Response, status
from app.utils.dependencies import Depends, get_auth_permission, get_request_id, get_response_id
from app.decorators import permissions, handlers,pipes,guards
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
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService,celeryService:CeleryService,bkgTaskService:BackgroundTaskService):
        super().__init__(dependencies=[Depends(BackgroundTaskService.populate_response_with_request_id)])
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService
        self.celeryService:CeleryService = celeryService
        self.bkgTaskService: BackgroundTaskService = bkgTaskService


    @UseRoles([Role.MFA_OTP])
    @UsePermission(permissions.JWTAssetPermission)
    @UseHandler(handlers.TemplateHandler)
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_template_mail']))
    @BaseHTTPRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE)
    def send_emailTemplate(self, template: str, scheduler: EmailTemplateSchedulerModel, x_request_id:str =Depends(get_request_id) ,authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()
        mail_content = scheduler.content
        meta = mail_content.meta.model_dump(mode='python')

        if template not in self.assetService.htmls:
            raise TemplateNotFoundError
        
        template: HTMLTemplate = self.assetService.htmls[template]
        _,data = template.build(mail_content.data)
    
        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            if scheduler.task_type == 'now' or scheduler.task_type == 'once':
                self.bkgTaskService.add_task( x_request_id,self.emailService.sendTemplateEmail, data, meta, template.images )

                return BASE_SUCCESS_RESPONSE
            self.celeryService.pingService()
            return  #TODO  if celery service status is either 4 or 5 
        
        return self.celeryService.trigger_task_from_scheduler(scheduler,data, meta, template.images)
    
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_custom_mail']))
    @BaseHTTPRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE)
    def send_customEmail(self, scheduler: CustomEmailSchedulerModel,request:Request,x_request_id:str =Depends(get_request_id), authPermission=Depends(get_auth_permission)):
        self.emailService.pingService()
        customEmail_content = scheduler.content
        meta = customEmail_content.meta.model_dump()
        content = (customEmail_content.html_content, customEmail_content.text_content)
       
        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            if scheduler.task_type == 'now' or scheduler.task_type == 'once':
                self.bkgTaskService.add_task(x_request_id,self.emailService.sendCustomEmail, content,meta,customEmail_content.images, customEmail_content.attachments)
                return BASE_SUCCESS_RESPONSE

            self.celeryService.pingService()
            return #TODO  if celery service status is either 4 or 5 th Status
        
        return self.celeryService.trigger_task_from_scheduler(scheduler,content,meta,customEmail_content.images, customEmail_content.attachments)
