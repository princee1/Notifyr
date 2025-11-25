from typing import Annotated, Callable, Literal
import aiohttp
from aiohttp_retry import Tuple
from app.classes.auth_permission import MustHave, Role
from app.classes.email import parse_mime_content
from app.classes.mail_provider import get_email_provider_name
from app.classes.template import CONTENT_HTML, CONTENT_TEXT, HTMLTemplate
from app.cost.email_cost import EmailCost
from app.decorators.interceptors import TaskCostInterceptor
from app.definition._service import BaseMiniService
from app.definition._utils_decorator import Pipe
from app.depends.class_dep import  EmailTracker
from app.depends.funcs_dep import get_profile, get_template
from app.interface.email import EmailSendInterface
from app.manager.broker_manager import Broker
from app.models.email_model import BaseEmailSchedulerModel, CustomEmailSchedulerModel, EmailTemplateSchedulerModel
from app.services.assets_service import AssetService
from app.services.celery_service import CeleryService, ChannelMiniService
from app.services.profile_service import ProfileService
from app.services.setting_service import SettingService
from app.services.config_service import ConfigService
from app.manager import TaskManager
from app.services.link_service import LinkService
from app.services.security_service import SecurityService
from app.container import Get, InjectInMethod
from app.definition._ressource import HTTPMethod, HTTPRessource, PingService, UseInterceptor, UseServiceLock, UseGuard, UseLimiter, UsePermission, BaseHTTPRessource, UseHandler, NextHandlerException, RessourceResponse, UsePipe, UseRoles
from app.services.email_service import EmailReaderService, EmailSenderService
from fastapi import Request, Response, status
from app.depends.dependencies import Depends, get_auth_permission
from app.decorators import permissions, handlers,pipes,guards
from app.depends.variables import email_verifier,wait_timeout_query
from app.utils.constant import CostConstant, StreamConstant
from app.utils.globals import DIRECTORY_SEPARATOR


EMAIL_PREFIX = "email"

TRACKING_META_CALLBACK = 0
TRACKING_META_URL = 1

DEFAULT_RESPONSE = {
    status.HTTP_202_ACCEPTED: {
        'message': 'email task received successfully'}
}

@UseRoles([Role.RELAY])
@UseHandler(handlers.ServiceAvailabilityHandler,handlers.CeleryTaskHandler)
@UsePermission(permissions.JWTRouteHTTPPermission)
@HTTPRessource(EMAIL_PREFIX)
class EmailRessource(BaseHTTPRessource):


    @staticmethod
    async def force_signature(scheduler:BaseEmailSchedulerModel):
        scheduler._signature = None
        return {}

    class TemplateSignatureValidationInjectionPipe(Pipe,pipes.InjectTemplateInterface):

        def __init__(self,bs4:bool=False):
            super().__init__(True)
            pipes.InjectTemplateInterface.__init__(self,Get(AssetService),'email',True)
            self.configService=Get(ConfigService)
            self.settingService = Get(SettingService)
            self.bs4 = bs4

        async def pipe(self,scheduler:BaseEmailSchedulerModel):
            if scheduler.signature == None:
                return {}

            signature:HTMLTemplate = self._inject_template(scheduler.signature.template)
            sign_data = scheduler.signature.data
            _,_signature = signature.build(sign_data,target_lang= self.settingService.ASSET_LANG,validate=True,bs4=self.bs4)
            scheduler._signature = _signature
            return {}
    
    @InjectInMethod()
    def __init__(self,emailReaderService:EmailReaderService, emailSender: EmailSenderService, configService: ConfigService, securityService: SecurityService,celeryService:CeleryService):
        super().__init__()

        self.emailService: EmailSenderService = emailSender
        self.configService: ConfigService = configService
        self.securityService: SecurityService = securityService
        self.celeryService:CeleryService = celeryService
        self.emailReaderService:EmailReaderService = emailReaderService

        self.linkService= Get(LinkService)
        self.settingService = Get(SettingService)

        self.exclude_meta =('as_contact','index','will_track','sender_type')


    @UseLimiter(limit_value="10/minutes")
    @UseRoles([Role.PUBLIC])
    @UsePermission(permissions.JWTAssetPermission('email','html',accept_none_template=True))
    @UsePipe(pipes.FilterAllowedSchemaPipe,before=False)
    @UseServiceLock(AssetService,lockType='reader')
    @UsePipe(pipes.TemplateParamsPipe('email','html',True))
    @UseHandler(handlers.AsyncIOHandler,handlers.TemplateHandler)
    @BaseHTTPRessource.HTTPRoute('/template/{template:path}',methods=[HTTPMethod.OPTIONS])
    def get_template_schema(self,request:Request,response:Response,template:str='',authPermission=Depends(get_auth_permission),wait_timeout: int | float = Depends(wait_timeout_query)):
        print(template)
        schemas = self.assetService.get_schema('email')
        if template in schemas:
            return schemas[template]
        return schemas


    @UseLimiter(limit_value='1000/minutes')
    @UseRoles([Role.MFA_OTP])
    @UseInterceptor(TaskCostInterceptor(),inject_meta=True)
    @PingService([ProfileService,EmailSenderService,CeleryService],is_manager=True)
    @UseServiceLock(ProfileService,EmailSenderService,CeleryService,AssetService,lockType='reader',check_status=False,as_manager =True)
    @UsePermission(permissions.TaskCostPermission(),permissions.JWTAssetPermission('email'),permissions.JWTSignatureAssetPermission())
    @UseHandler(handlers.AsyncIOHandler(),handlers.MiniServiceHandler,handlers.TemplateHandler(),handlers.CostHandler,handlers.ContactsHandler(),handlers.ProfileHandler)
    @UsePipe(pipes.OffloadedTaskResponsePipe(),before=False)
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_template_mail']),guards.TrackGuard())
    @UsePipe(pipes.MiniServiceInjectorPipe(EmailSenderService,'email'),pipes.MiniServiceInjectorPipe(CeleryService,'channel'))
    @UsePipe(pipes.TemplateSignatureQueryPipe(),TemplateSignatureValidationInjectionPipe(True),force_signature,pipes.RegisterSchedulerPipe,pipes.CeleryTaskPipe(),pipes.TemplateParamsPipe('email','html'),pipes.ContentIndexPipe(),pipes.TemplateValidationInjectionPipe('email','data',''),pipes.ContactToInfoPipe('email','meta.To'),)
    @BaseHTTPRessource.HTTPRoute("/template/{profile}/{template:path}", responses=DEFAULT_RESPONSE,cost_definition=CostConstant.email_template)
    async def send_emailTemplate(self,profile:str,email:Annotated[EmailSendInterface|BaseMiniService,Depends(get_profile)],channel:Annotated[ChannelMiniService,Depends(get_profile)],cost:Annotated[EmailCost,Depends(EmailCost)],template: Annotated[HTMLTemplate,Depends(get_template)], scheduler: EmailTemplateSchedulerModel, request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],taskManager: Annotated[TaskManager, Depends(TaskManager)],tracker:Annotated[EmailTracker,Depends(EmailTracker)],wait_timeout: int | float = Depends(wait_timeout_query), authPermission=Depends(get_auth_permission)):

        signature:Tuple[str,str]|None = scheduler._signature
        for mail_content in scheduler.content:
            
            datas = []
            index = mail_content.index 
            To = mail_content.meta.To
            
            if tracker.will_track:
                for j,tracking_event_data in enumerate(tracker.pipe_email_data(email,mail_content)):
                    tracking_meta=self._generate_tracking_metadata(broker,To,tracking_event_data,index,j,scheduler)
                    if tracking_meta == None:
                        continue

                    _,data = template.build(mail_content.data,self.settingService.ASSET_LANG,tracking_meta[TRACKING_META_CALLBACK],tracking_url=tracking_meta[TRACKING_META_URL], signature=signature)
                    data = parse_mime_content(data,mail_content.mimeType)
                    datas.append(data)
            else:
                
                _,data = template.build(mail_content.data,self.settingService.ASSET_LANG,signature=signature)
                datas = parse_mime_content(data,mail_content.mimeType)
                mail_content.meta._Message_ID = tracker.make_msgid

            meta = mail_content.meta.model_dump(mode='python',exclude=self.exclude_meta)
            await taskManager.offload_task(len(To),0,index,email.sendTemplateEmail,datas, meta, template.images,email_profile=email.miniService_id)

        return taskManager.results
    

    @UseLimiter(limit_value='10/minutes')
    @UseHandler(handlers.AsyncIOHandler(),handlers.MiniServiceHandler,handlers.CostHandler, handlers.ContactsHandler(),handlers.TemplateHandler(),handlers.ProfileHandler)
    @PingService([ProfileService,EmailSenderService,CeleryService],is_manager=True)
    @UseServiceLock(ProfileService,EmailSenderService,lockType='reader',check_status=False,as_manager =True)
    @UsePermission(permissions.TaskCostPermission(),permissions.JWTSignatureAssetPermission())
    @UsePipe(pipes.MiniServiceInjectorPipe(EmailSenderService,'email'),pipes.MiniServiceInjectorPipe(CeleryService,'channel'))
    @UsePipe(pipes.OffloadedTaskResponsePipe(),before=False)
    @UseInterceptor(TaskCostInterceptor(),inject_meta=True)
    @UsePipe(pipes.TemplateSignatureQueryPipe,TemplateSignatureValidationInjectionPipe,force_signature,pipes.RegisterSchedulerPipe,pipes.CeleryTaskPipe,pipes.ContentIndexPipe,pipes.ContactToInfoPipe('email','meta.To'))
    @UseGuard(guards.CeleryTaskGuard(task_names=['task_send_custom_mail']),guards.TrackGuard())
    @BaseHTTPRessource.HTTPRoute("/custom/{profile}/", responses=DEFAULT_RESPONSE,cost_definition=CostConstant.email_template)
    async def send_customEmail(self,profile:str,email:Annotated[EmailSendInterface|BaseMiniService,Depends(get_profile)],channel:Annotated[ChannelMiniService,Depends(get_profile)],cost:Annotated[EmailCost,Depends(EmailCost)],scheduler: CustomEmailSchedulerModel,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],taskManager: Annotated[TaskManager, Depends(TaskManager)],tracker:Annotated[EmailTracker,Depends(EmailTracker)], authPermission=Depends(get_auth_permission)):
        signature:Tuple[str,str] = scheduler._signature
          
        for customEmail_content in scheduler.content:
            
            content = (customEmail_content.html_content, customEmail_content.text_content)
            contents = []
            index = customEmail_content.index
            To = customEmail_content.meta.To

            if tracker.will_track:
                for j,tracking_event_data in enumerate(tracker.pipe_email_data(email,customEmail_content)):
                    tracking_meta = self._generate_tracking_metadata(broker,To,tracking_event_data,index,j,scheduler)
                    if tracking_meta == None:
                        continue
                    tracking_link_callback,tracking_url = tracking_meta[TRACKING_META_CALLBACK], tracking_meta[TRACKING_META_URL]

                    email_content = tracking_link_callback(content[CONTENT_HTML]),tracking_link_callback(content[CONTENT_TEXT])
                    email_content = content[CONTENT_HTML],content[CONTENT_TEXT]

                    if signature!=None:
                        email_content = email_content[CONTENT_HTML],email_content[CONTENT_TEXT]+("\n"*4)+signature[1]

                    contents.append(email_content)
            else:
                if signature != None:
                    _content = content[CONTENT_HTML],content[CONTENT_TEXT]+"\n"+signature[1]
                else:
                    _content = content
                contents = _content
                customEmail_content.meta._Message_ID = tracker.make_msgid

            meta = customEmail_content.meta.model_dump(mode='python',exclude=self.exclude_meta)
            await taskManager.offload_task(len(To),0,index,email.sendCustomEmail,contents,meta,customEmail_content.images, customEmail_content.attachments,email_profile=email.miniService_id)
        return taskManager.results
    
    
    @UseLimiter(limit_value='10/day')
    @UseRoles([Role.PUBLIC])
    @UseHandler(handlers.EmailRelatedHandler())
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
    
    async def on_shutdown(self):
        await super().on_shutdown()
        self.emailReaderService.cancel_jobs()
    
    def _get_esp(self,email):
        esp = get_email_provider_name(email)
        if esp != 'Untracked Provider':
            return {'esp':esp}
        else:
            return {}

    def _generate_tracking_metadata(self,broker:Broker,To:list[str],tracking_event_data:dict,index:int,j:int,scheduler:CustomEmailSchedulerModel|EmailTemplateSchedulerModel)->Tuple[Callable,str|None]:
        if tracking_event_data == None:
            scheduler._errors[index] = {
                'message':'Cant track more than one email when it is set as individual at the moment',
                'key':To,
                'index':index
            }
            return None
        
        add_params = self._get_esp(To[j])
        (event_tracking,email_tracking),eid,contact_id = tracking_event_data['track'],tracking_event_data['email_id'],tracking_event_data['contact_id']
        

        broker.stream(StreamConstant.EMAIL_TRACKING,email_tracking)
        broker.stream(StreamConstant.EMAIL_EVENT_STREAM,event_tracking)
        tracking_url = self.linkService.create_tracking_pixel('raw_url',eid,contact_id,)
        tracking_link_callback = self.linkService.create_link_re(eid,add_params=add_params,contact_id=contact_id) # FIXME if its a list change it 
        
        return tracking_link_callback,tracking_url
        