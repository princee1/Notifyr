from typing import Literal
import aiohttp
from app.classes.auth_permission import MustHave, Role
from app.classes.template import HTMLTemplate
from app.definition._service import ServiceStatus
from app.models.email_model import CustomEmailModel, EmailSpamDetectionModel, EmailTemplateModel
from app.services.celery_service import TaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService
from app.container import InjectInMethod
from app.definition._ressource import HTTPMethod, HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UsePipe, UseRoles
from app.services.email_service import EmailSenderService
from fastapi import   Request, Response, status
from app.depends.dependencies import Depends, get_auth_permission, get_request_id
from app.decorators import permissions, handlers,pipes,guards
from app.classes.celery import SchedulerModel
from app.depends.variables import populate_response_with_request_id,track_email,email_verifier


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
@PingService([EmailSenderService])
@HTTPRessource(EMAIL_PREFIX)
class EmailTemplateRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService,celeryService:CeleryService,bkgTaskService:TaskService):
        super().__init__(dependencies=[Depends(populate_response_with_request_id)])
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService
        self.celeryService:CeleryService = celeryService
        self.taskService: TaskService = bkgTaskService

    
    @UseLimiter(limit_value="10/minutes")
    @UseRoles([Role.PUBLIC])
    @UsePipe(pipes.TemplateParamsPipe('html','html',True))
    @UseHandler(handlers.TemplateHandler)
    @BaseHTTPRessource.HTTPRoute('/template/',methods=[HTTPMethod.OPTIONS])
    def get_template_schema(self,request:Request,response:Response,authPermission=Depends(get_auth_permission),template:str=''):
        schemas = self.assetService.get_schema('html')
        if template in schemas:
            return schemas[template]
        return schemas


    @UseLimiter(limit_value='10000/minutes')
    @UseRoles([Role.MFA_OTP])
    @UsePermission(permissions.JWTAssetPermission('html'))
    @UseHandler(handlers.TemplateHandler)
    @UsePipe(pipes.CeleryTaskPipe,pipes.TemplateParamsPipe('html','html'))
    @UsePipe(pipes.OffloadedTaskResponsePipe,before=False)
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_template_mail']))
    @BaseHTTPRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE)
    async def send_emailTemplate(self, template: str, scheduler: EmailTemplateSchedulerModel, request:Request,response:Response,x_request_id:str =Depends(get_request_id) ,authPermission=Depends(get_auth_permission)):
        mail_content = scheduler.content

        emailMetaData=scheduler.content.meta
        emailMetaData.Disposition_Notification_To = self.configService.SMTP_EMAIL
        emailMetaData.Return_Receipt_To = self.configService.SMTP_EMAIL

        meta = mail_content.meta.model_dump(mode='python')

        template: HTMLTemplate = self.assetService.html[template]
        _,data = template.build(mail_content.data,self.configService.ASSET_LANG)
        
        # if self.celeryService.service_status != ServiceStatus.AVAILABLE:
            # if scheduler.task_type == TaskType.NOW.value:
            #     return await self.taskService.add_task( scheduler.heaviness,x_request_id,0,None,self.emailService.sendTemplateEmail, data, meta, template.images )
        return self.celeryService.trigger_task_from_scheduler(scheduler,None,data, meta, template.images)
    
    @UseLimiter(limit_value='10000/minutes')
    @UsePipe(pipes.CeleryTaskPipe)
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_custom_mail']))
    @UsePipe(pipes.OffloadedTaskResponsePipe,before=False)
    @BaseHTTPRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE)
    async def send_customEmail(self, scheduler: CustomEmailSchedulerModel,request:Request,response:Response,x_request_id:str =Depends(get_request_id), authPermission=Depends(get_auth_permission)):
        customEmail_content = scheduler.content
        content = (customEmail_content.html_content, customEmail_content.text_content)

        emailMetaData=scheduler.content.meta
        emailMetaData.Disposition_Notification_To = self.configService.SMTP_EMAIL
        emailMetaData.Return_Receipt_To = self.configService.SMTP_EMAIL
    
        meta = customEmail_content.meta.model_dump()

        #if self.celeryService.service_status != ServiceStatus.AVAILABLE:
        # if scheduler.task_type == TaskType.NOW.value:
        #         return await self.taskService.add_task(scheduler.heaviness,x_request_id,0,None,self.emailService.sendCustomEmail, content,meta,customEmail_content.images, customEmail_content.attachments)
        return self.celeryService.trigger_task_from_scheduler(scheduler,None,content,meta,customEmail_content.images, customEmail_content.attachments)



    @UseRoles(options=[MustHave(Role.ADMIN)])
    @BaseHTTPRessource.HTTPRoute("/domain/",methods=[HTTPMethod.GET],mount=False)
    async def verify_domain_hosting(self,):
        ...

    @UseLimiter(limit_value='10/day')
    @UseRoles([Role.PUBLIC])
    @UseHandler(handlers.EmailRelatedHandler)
    @BaseHTTPRessource.HTTPRoute("/spam-detection/",methods=[HTTPMethod.POST],mount=False)
    async def email_spam_detection(self,emailSpam:EmailSpamDetectionModel, request:Request):
        ...


    @UseLimiter(limit_value='10/day')
    @UseRoles([Role.PUBLIC])
    @UseHandler(handlers.EmailRelatedHandler)
    @UsePipe(pipes.verify_email_pipe)
    @BaseHTTPRessource.HTTPRoute("/verify/{email}",methods=[HTTPMethod.GET],mount=False)
    async def verify_email(self,email:str,request:Request,verifier:Literal['smtp','reacherhq']=Depends(email_verifier)):
        if verifier == 'smtp':
            return self.emailService.verify_same_domain_email(email)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://localhost:8088/verify/{email}') as resp:
                if resp.status == 200:
                    return await resp.json()
            return {"error": f"Failed to verify email. Status code: {resp.status}"}
        
