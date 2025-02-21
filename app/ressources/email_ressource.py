from app.classes.auth_permission import MustHave, Role
from app.classes.template import HTMLTemplate
from app.definition._service import ServiceStatus
from app.models.email_model import CustomEmailModel, EmailTemplateModel
from app.services.celery_service import BackgroundTaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.container import GetDepends, InjectInMethod
from app.definition._ressource import HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UsePipe, UseRoles
from app.services.email_service import EmailSenderService
from fastapi import  Header, Request, status
from app.utils.dependencies import Depends, get_auth_permission, get_request_id, get_response_id
from app.decorators import permissions, handlers,pipes,guards
from app.classes.celery import  CeleryTask, SchedulerModel


class EmailTemplateSchedulerModel(SchedulerModel):
    content: EmailTemplateModel

class CustomEmailSchedulerModel(SchedulerModel):
    content: CustomEmailModel


EMAIL_PREFIX = "email"

DEFAULT_RESPONSE = {
    status.HTTP_202_ACCEPTED: {
        'message': 'email task received successfully'}
}


@UseRoles([Role.RELAY])
@UseHandler(handlers.ServiceAvailabilityHandler,handlers.CeleryTaskHandler)
@UsePermission(permissions.JWTRouteHTTPPermission)
@UsePipe(pipes.CeleryTaskPipe)
@PingService([EmailSenderService])
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
    @UsePermission(permissions.JWTAssetPermission('html'))
    @UseHandler(handlers.TemplateHandler)
    @UsePipe(pipes.TemplateParamsPipe('html'))
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_template_mail']))
    @BaseHTTPRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE)
    def send_emailTemplate(self, template: str, scheduler: EmailTemplateSchedulerModel, x_request_id:str =Depends(get_request_id) ,authPermission=Depends(get_auth_permission)):
        mail_content = scheduler.content
        meta = mail_content.meta.model_dump(mode='python')
        
        template: HTMLTemplate = self.assetService.html[template]
        _,data = template.build(mail_content.data,self.configService.ASSET_LANG)
    
        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            if scheduler.task_type == 'now' or scheduler.task_type == 'once':
                return self.bkgTaskService.add_task( scheduler.heaviness,x_request_id,self.emailService.sendTemplateEmail, data, meta, template.images )

        return self.celeryService.trigger_task_from_scheduler(scheduler,data, meta, template.images)
    
    @UseLimiter(limit_value='10000/minute')
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_custom_mail']))
    @BaseHTTPRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE)
    def send_customEmail(self, scheduler: CustomEmailSchedulerModel,request:Request,x_request_id:str =Depends(get_request_id), authPermission=Depends(get_auth_permission)):
        customEmail_content = scheduler.content
        meta = customEmail_content.meta.model_dump()
        content = (customEmail_content.html_content, customEmail_content.text_content)
       
        if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            if scheduler.task_type == 'now' or scheduler.task_type == 'once':
                return self.bkgTaskService.add_task(scheduler.heaviness,x_request_id,self.emailService.sendCustomEmail, content,meta,customEmail_content.images, customEmail_content.attachments)
            
        return self.celeryService.trigger_task_from_scheduler(scheduler,content,meta,customEmail_content.images, customEmail_content.attachments)
