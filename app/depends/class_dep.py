from typing import Annotated, Literal,TypedDict
from urllib.parse import urlparse
from fastapi import  Depends,  Query, Request, Response
from pydantic import BaseModel
from app.classes.broker import SubjectType
from app.classes.mail_provider import get_email_provider_name
from app.classes.scheduler import TimedeltaSchedulerModel
from app.definition._error import ServerFileError
from app.definition._interface import Interface
from app.interface.email import EmailInterface, EmailSendInterface
from app.models.call_model import BaseVoiceCallModel
from app.models.data_ingest_model import DataIngestFileModel
from app.models.email_model import CustomEmailModel, EmailStatus, EmailTemplateModel, TrackingEmailEventORM
from app.models.link_model import LinkORM
from app.models.sms_model import OnGoingBaseSMSModel
from app.models.twilio_model import CallEventORM, CallStatusEnum, SMSEventORM, SMSStatusEnum
from app.services.config_service import ConfigService
from app.container import Get
from app.utils.constant import ParseStrategy, SpecialKeyAttributesConstant
from app.utils.validation import url_validator
from .variables import *
from app.services.link_service import LinkService
from app.utils.helper import get_value_in_list,  uuid_v1_mc
from datetime import datetime, timedelta, timezone
import random
from time import time

from .variables import _wrap_checker

track:Callable[[Request],bool] = get_query_params('track','false',True,raise_except=True)

class ToPydanticModelInterface(Interface):

    def __init__(self):
       super().__init__()

    def to_model(self)->BaseModel:
        ...


class TrackerInterface:

    def __init__(self,flag):
        self.will_track=flag

class EmailTracker(TrackerInterface):

    def __init__(self,track_email:bool = Depends(track)):
        super().__init__(track_email)
        self.configService: ConfigService = Get(ConfigService)

    def make_msgid(self,email_id: str = None):
        email_id = '' if email_id is None else email_id
        timeval = int(time() * 1000000)
        randval = random.getrandbits(8)
        return f"<{timeval}.{randval}.{email_id}@{self.configService.DOMAIN_NAME}>"
            

    def pipe_to(self,content:EmailTemplateModel|CustomEmailModel):
        if not content.meta.as_individual and  len(content.meta.To) >1 and self.will_track:
                return False
        elif not content.meta.as_individual:
            content.meta.To = [','.join(content.meta.To)]
        
        return True

    def pipe_email_data(self,email:EmailSendInterface |EmailInterface,content:EmailTemplateModel|CustomEmailModel, spam:tuple[float,str]=(100,'no-spam')):
        
        spam_confidence,spam_label = spam        
        emailMetaData=content.meta

        contact_ids = getattr(content.meta,SpecialKeyAttributesConstant.CONTACT_SPECIAL_KEY_ATTRIBUTES,[])

        if not self.pipe_to(content):
            yield None

        for i,to in enumerate(emailMetaData.To):
            temp_email_id = str(uuid_v1_mc())
            message_id = self.make_msgid(temp_email_id)
        
            email_id = None
            track =  {
                    'email_id':email_id,
                    'message_id':message_id
                }
            emailMetaData._Message_ID.append(message_id)

            if self.will_track:
                                
                email_id = temp_email_id
                track['email_id'] = email_id
                emailMetaData._X_Email_ID.append(email_id)

                recipient = to
                subject = emailMetaData.Subject

                emailMetaData._Disposition_Notification_To = email.disposition_notification_to
                emailMetaData._Return_Receipt_To = email.return_receipt_to
                
                contact_id = get_value_in_list(contact_ids,i)

                temp = self._create_tracking_event_data(spam_confidence, spam_label, email_id, message_id, recipient, subject,contact_id=contact_id)
                temp ={'track':temp,'contact_id':contact_id }
                track.update(temp)
            
            yield track 

    def _create_tracking_event_data(self, spam_confidence, spam_label, email_id, message_id, recipient, subject,contact_id=None):
        # Convert datetime fields to timezone-aware ISO 8601 string representation
        now = datetime.now(timezone.utc)
        expired_tracking_date = (now + timedelta(days=30)).isoformat()

        esp_provider = get_email_provider_name(recipient)
        description=f'Notifyr server received the request'
        event = TrackingEmailEventORM.JSON(event_id=str(uuid_v1_mc()),description=description,esp_provider=esp_provider,email_id=email_id,current_event=EmailStatus.RECEIVED.value)
                # Create the EmailTrackingORM object
        tracking= {
                    "recipient": recipient,
                    "subject":subject,
                    "email_id": email_id,
                    'contact_id':contact_id,
                    "message_id": message_id,
                    "esp_provider":esp_provider,
                    "spam_detection_confidence": spam_confidence,
                    "spam_label": spam_label,
                    "date_sent": now.isoformat(),
                    "last_update": now.isoformat(),
                    'email_current_status':EmailStatus.RECEIVED.value,
                    "expired_tracking_date": expired_tracking_date,
                }
            
        return (event,tracking) 

class TwilioTracker(TrackerInterface):

    def __init__(self, track_twilio: bool = Depends(track)):
        super().__init__(track_twilio)

    def pipe_sms_track_event_data(self, content: OnGoingBaseSMSModel, contact_id=None):
        now = datetime.now(timezone.utc)
        expired_tracking_date = (now + timedelta(days=30)).isoformat()
        contact_ids = getattr(content,SpecialKeyAttributesConstant.CONTACT_SPECIAL_KEY_ATTRIBUTES,[])

        for i,to in enumerate(content.to):
            
            if self.will_track:
                contact_id = get_value_in_list(contact_ids,i)
            
                # if len(content.to) >1:
                #         raise HTTPException(status_code=400,detail='Can only track one sms at a time')
                
                twilio_id = str(uuid_v1_mc())
                # Create the SMS sent event
                sent_event = SMSEventORM.JSON(
                    event_id=str(uuid_v1_mc()),
                    sms_id=twilio_id,
                    sms_sid=None,
                    direction='O',
                    current_event=SMSStatusEnum.RECEIVED.value,
                    description="SMS sent successfully",
                    date_event_received=now.isoformat()
                )

                tracking_data = {
                    'sms_id': twilio_id,
                    'contact_id': contact_id,
                    'recipient': to,
                    'sender': content.from_,
                    'date_sent': now.isoformat(),
                    'last_update': now.isoformat(),
                    'expired_tracking_date': expired_tracking_date,
                    'sms_current_status': SMSStatusEnum.RECEIVED.value
                }

                yield twilio_id,sent_event, tracking_data

    def pipe_call_track_event_data(self, content: BaseVoiceCallModel, contact_id=None):
        now = datetime.now(timezone.utc)
        expired_tracking_date = (now + timedelta(days=30)).isoformat()
        
        contact_ids = getattr(content,SpecialKeyAttributesConstant.CONTACT_SPECIAL_KEY_ATTRIBUTES,[])

        for i,to in enumerate(content.to):

            if self.will_track:
                contact_id = get_value_in_list(contact_ids,i)
                
                twilio_id = str(uuid_v1_mc())
                # if len(content.to) >1:
                #     raise HTTPException(status_code=400,detail='Can only track one phone at a time')

                # Create the Call sent event
                sent_event = CallEventORM.JSON(
                    event_id=str(uuid_v1_mc()),
                    call_sid=None,
                    call_id=twilio_id,
                    direction='O',
                    current_event=CallStatusEnum.RECEIVED.value,
                    description="Call initiated successfully",
                    date_event_received=now.isoformat(),
                    city=None,
                    country=None,
                    state=None
                )

                tracking_data = {
                    'call_id': twilio_id,
                    'contact_id': contact_id,
                    'recipient': to,
                    'sender': content._from,
                    'date_sent': now.isoformat(),
                    'last_update': now.isoformat(),
                    'expired_tracking_date': expired_tracking_date,
                    'call_current_status': CallStatusEnum.RECEIVED.value
                }

                yield twilio_id,sent_event, tracking_data



class SubjectParams: #NOTE rename to ReactiveParams

    subject_id_params:Callable[[Request],str] = get_query_params('subject_id',None)

    sid_type_params:Callable[[Request],str] = get_query_params("sid_type","plain",checker=_wrap_checker('sid_type', lambda v: v in get_args(SubjectType), choices=list(get_args(SubjectType))))


    def __init__(self,request:Request,sid_type:Annotated[str|None,Depends(sid_type_params)],subject_id:Annotated[str|None,Depends(subject_id_params)]):
        self.sid_type = sid_type
        self.subject_id = subject_id,
        if isinstance(self.subject_id,tuple):
            self.subject_id = list(self.subject_id)[0]

class LinkQuery:

    class ServerScopedParams(TypedDict):
        client_id:str | None = None
        group_id:str|None = None
        contact_id:str|None = None
        session_id:str|None = None
        message_id:str|None = None
        link_id:str|None = None
        subject_id:str|None = None

    class IdsTypeParams(TypedDict):
        cid:str |None = None
        gid:str |None = None
        lid:str |None = None
        ctid:str |None = None

        cid_type :Literal['client','contact']
        sid_type: SubjectType

    server_scoped_params = ["client_id", "group_id", "contact_id", "session_id","message_id","link_id","subject_id",'r','esp']
    ids_type = ["cid","gid","lid","ctid","sid_type"]
    
    def __init__(self, request: Request):
        self.request = request
        self._filter_params()
        self.configService:ConfigService = Get(ConfigService)
        self.linkService:LinkService = Get(LinkService)
        self.base_url = self.linkService.BASE_URL('')
    
    def __getitem__(self,params)->str|None:
        return self.request.query_params.get(params,None)

    def _filter_params(self) -> dict:
        scoped_params ={}
        ids_type_params = {}
        self._link_params = {}

        for key,value in self.request.query_params.items():

            if key in self.ids_type:
                ids_type_params[key] = value

            elif key in self.server_scoped_params:
                scoped_params[key]=value
            else:
                self._link_params[key] =value

        self.server_scoped = self.ServerScopedParams(**scoped_params) 
        self.ids_type_params = self.IdsTypeParams(**ids_type_params)

    @property
    def all_params(self):
        return self.request._query_params.__str__()

    @property
    def raw_link_params(self):
        return "&".join([ f'{key}={value}' for key,value in self._link_params.items()])
    
    def raw_filtered_out_params(self,attr:Literal['server_scoped','ids_type_params'],include=()):
        return "&".join([ f'{key}={value}' for key,value in getattr(self,attr).items() if key in include])
    
    def create_link(self,link:LinkORM|None|str,path:str='',include_scoped_out=(),include_ids_type=()):
        if link == None:
            url = self.request.url.netloc
        elif isinstance(link,LinkORM):
            url = link.link_url
        elif isinstance(link,str):
            url = link
            
        if not url.endswith("/"):
            url+="/"

        path = path if path else ""

        if path.startswith('/'):
            path = path[1:]

        url+=path
        url+="?"
        url+=self.raw_link_params
        url+=self.raw_filtered_out_params('server_scoped',include_scoped_out)
        url+=self.raw_filtered_out_params('ids_type_params',include_ids_type)
        return url
    
    @property
    def subject_id(self):
        sid_type = self.ids_type_params.get('sid_type','plain')
        match sid_type:
            case 'message':
                return sid_type,self.server_scoped.get('message_id',None)
            case 'contact':
                return sid_type,self.server_scoped.get("contact_id",None)
            case 'plain':
                return sid_type,self.server_scoped.get("subject_id",None)
            case 'session':
                return sid_type,self.server_scoped.get("session_id",None)
            case _:
                return sid_type,self.server_scoped.get('subject_id',None)
            
    @property
    def redirect_url(self):
        redirect_url = self.request.query_params.get('r',None)
        if not url_validator(redirect_url):
            raise ServerFileError('app/static/error-404-page/index.html',status_code=404)

        if urlparse(redirect_url).netloc == self.base_url:
            redirect_url = redirect_url.replace(self.base_url,'')
        return redirect_url

    @property
    def is_same_redirect_url(self):
        redirect_url = self.request.query_params.get('r',None)
        return urlparse(redirect_url).netloc == self.base_url
    
class CampaignQuery:
    
    def __init__(self,request:Request):
        self.request = request

        self.utm_source = self.request.query_params.get("utm_source", None)
        self.utm_medium = self.request.query_params.get("utm_medium", None)
        self.utm_campaign = self.request.query_params.get("utm_campaign", None)
        self.utm_term = self.request.query_params.get("utm_term", None)
        self.utm_content = self.request.query_params.get("utm_content", None)

class ObjectsSearch:

    def __init__(self,recursive:bool=Query(True),match:str=Query(None),version_id:str=Query(None),assets:bool=Query(False)):
        self.recursive = recursive
        self.match = match
        self.version_id = version_id
        self.assets = assets
        self.is_file:bool = None


class FileDataIngestQuery(ToPydanticModelInterface):

    collection_name_query: Callable[[Request], str] = get_query_params('collection_name', raise_except=True)

    lang_query: Callable[[Request], str] = get_query_params('lang', default='en',raise_except=True)

    content_type_query: Callable[[Request], str | None] = get_query_params('content_type', default=None)

    expires_query: Callable[[Request], int| None] = get_query_params('expires', default=None,parse=True,raise_except=False,return_none=True)

    defer_by_query: Callable[[Request], int | None] = get_query_params('defer_by',default=None,parse=True,raise_except=False,return_none=True)

    strategy_query: Callable[[Request], ParseStrategy] = get_query_params('strategy','semantic',raise_except=True,checker=_wrap_checker('strategy',predicate=lambda v: v in [m.lower() for m in ParseStrategy._member_names_], choices=[m.lower() for m in ParseStrategy._member_names_]))

    use_docling_query: Callable[[Request], bool] = get_query_params('use_docling',default='false',parse=True)


    def __init__(
        self,
        collection_name: str = Depends(collection_name_query),
        lang: str = Depends(lang_query),
        content_type: str | None = Depends(content_type_query),
        expires: int | None = Depends(expires_query),
        defer_by: int | None = Depends(defer_by_query),
        strategy: ParseStrategy = Depends(strategy_query),
        use_docling: bool = Depends(use_docling_query),
    ):
        self.expires = 1 if expires == None else expires
        self.defer_by = 1 if expires == None else defer_by
        self.collection_name = collection_name
        self.lang = lang
        self.content_type = content_type
        self.strategy = strategy
        self.use_docling = use_docling

    
    def __repr__(self):
        return f'FileDataIngestQuery(collection_name={self.collection_name},expires={self.expires})'

    def to_model(self):
        return DataIngestFileModel(
            collection_name=self.collection_name,
            lang=self.lang,
            category=self.content_type,
            expires=TimedeltaSchedulerModel(seconds=self.expires),
            defer_by=TimedeltaSchedulerModel(seconds=self.defer_by),
            strategy=self.strategy,
            use_docling=self.use_docling
        )

