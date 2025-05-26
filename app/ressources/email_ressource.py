from typing import Annotated, Literal
import aiohttp
from app.classes.auth_permission import MustHave, Role
from app.classes.email import parse_mime_content
from app.classes.template import HTMLTemplate
from app.depends.class_dep import Broker, EmailTracker
from app.depends.funcs_dep import get_task
from app.models.email_model import CustomEmailModel, EmailSpamDetectionModel, EmailTemplateModel
from app.services.celery_service import TaskManager, TaskService, CeleryService
from app.services.config_service import ConfigService
from app.services.link_service import LinkService
from app.services.security_service import SecurityService
from app.container import Get, InjectInMethod
from app.definition._ressource import HTTPMethod, HTTPRessource, PingService, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UsePipe, UseRoles
from app.services.email_service import EmailReaderService, EmailSenderService
from fastapi import   Request, Response, status
from app.depends.dependencies import Depends, get_auth_permission
from app.decorators import permissions, handlers,pipes,guards
from app.classes.celery import SchedulerModel
from app.depends.variables import populate_response_with_request_id,email_verifier
from app.utils.constant import StreamConstant
from app.utils.helper import APIFilterInject


class EmailTemplateSchedulerModel(SchedulerModel):
    content: EmailTemplateModel

class CustomEmailSchedulerModel(SchedulerModel):
    content: CustomEmailModel


EMAIL_PREFIX = "email"

DEFAULT_RESPONSE = {
    status.HTTP_202_ACCEPTED: {
        'message': 'email task received successfully'}
}

@APIFilterInject
async def pipe_email_track(scheduler:CustomEmailSchedulerModel| EmailTemplateSchedulerModel,tracker:EmailTracker):
    configService = Get(ConfigService)
    content:EmailTemplateModel|CustomEmailModel = scheduler.content
    emailMetaData=content.meta

    if tracker.will_track:

        tracker.recipient = emailMetaData.To
        tracker.subject = emailMetaData.Subject

        emailMetaData.Disposition_Notification_To = configService.SMTP_EMAIL
        emailMetaData.Return_Receipt_To = configService.SMTP_EMAIL
        
        emailMetaData.X_Email_ID = tracker.email_id

    emailMetaData.Message_ID = tracker.message_id
    return {'scheduler':scheduler,'tracker':tracker}

@UseRoles([Role.RELAY])
@UseHandler(handlers.ServiceAvailabilityHandler,handlers.CeleryTaskHandler)
@UsePermission(permissions.JWTRouteHTTPPermission)
@PingService([EmailSenderService])
@HTTPRessource(EMAIL_PREFIX)
class EmailTemplateRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,emailReaderService:EmailReaderService, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService,celeryService:CeleryService,taskService:TaskService):
        super().__init__()
        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService
        self.celeryService:CeleryService = celeryService
        self.taskService: TaskService = taskService
        self.emailReaderService:EmailReaderService = emailReaderService
        self.linkService= Get(LinkService)

    
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
    @UsePipe(pipe_email_track,pipes.CeleryTaskPipe,pipes.TemplateParamsPipe('html','html'))
    @UsePipe(pipes.OffloadedTaskResponsePipe(),before=False)
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_template_mail']),guards.TrackGuard)
    @BaseHTTPRessource.HTTPRoute("/template/{template}", responses=DEFAULT_RESPONSE,dependencies=[Depends(populate_response_with_request_id)])
    async def send_emailTemplate(self, template: str, scheduler: EmailTemplateSchedulerModel, request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],taskManager: Annotated[TaskManager, Depends(get_task)],tracker:Annotated[EmailTracker,Depends(EmailTracker)], authPermission=Depends(get_auth_permission)):
        mail_content = scheduler.content
        meta = mail_content.meta.model_dump(mode='python')
        template: HTMLTemplate = self.assetService.html[template]
        
        if tracker.will_track:
            template = template.clone()
            email_tracking = tracker.track_event_data()
            self.linkService.create_tracking_pixel(template,tracker.email_id)
            broker.stream(StreamConstant.EMAIL_TRACKING,email_tracking)

        _,data = template.build(mail_content.data,self.configService.ASSET_LANG)
        data = parse_mime_content(data,mail_content.mimeType)
        
        await taskManager.offload_task('worker_focus',scheduler,0,None,None,data, meta, template.images,tracker.message_tracking_id,contact_id=None)
        return taskManager.results
    
    @UseLimiter(limit_value='10000/minutes')
    @UsePipe(pipe_email_track,pipes.CeleryTaskPipe)
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_custom_mail']),guards.TrackGuard)
    @UsePipe(pipes.OffloadedTaskResponsePipe(),before=False)
    @BaseHTTPRessource.HTTPRoute("/custom/", responses=DEFAULT_RESPONSE,dependencies= [Depends(populate_response_with_request_id)])
    async def send_customEmail(self, scheduler: CustomEmailSchedulerModel,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],taskManager: Annotated[TaskManager, Depends(get_task)],tracker:Annotated[EmailTracker,Depends(EmailTracker)], authPermission=Depends(get_auth_permission)):
        customEmail_content = scheduler.content
        content = (customEmail_content.html_content, customEmail_content.text_content)

        meta = customEmail_content.meta.model_dump()
        if tracker.will_track:
            email_tracking = tracker.track_event_data()
            broker.stream(StreamConstant.EMAIL_TRACKING,email_tracking)
            
        await taskManager.offload_task('worker_focus',scheduler,0,None,None,content,meta,customEmail_content.images, customEmail_content.attachments,tracker.message_tracking_id,contact_id =None)
        return taskManager.results


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
        

    def on_startup(self):
        super().on_startup()
        self.emailReaderService.start_jobs()
    
    def on_shutdown(self):
        super().on_shutdown()
        self.emailReaderService.cancel_jobs()