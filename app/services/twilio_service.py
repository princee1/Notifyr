"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

import functools
from typing import Annotated, Callable, Coroutine, Literal
from fastapi import HTTPException, Header, Request
import requests
from app.classes.profiles import ProfileModelException,ProfileState
from app.classes.template import SMSTemplate
from app.definition import _service
from app.interface.profile_event import ProfileEventInterface
from app.interface.twilio import TwilioInterface
from app.models.otp_model import GatherDtmfOTPModel, GatherOTPBaseModel, GatherSpeechOTPModel, OTPModel
from app.models.communication_model import TwilioProfileModel
from app.models.twilio_model import CallEventORM, CallStatusEnum, SMSEventORM, SMSStatusEnum
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.vault_service import VaultService
from app.utils.constant import StreamConstant
from app.utils.globals import APP_MODE, ApplicationMode
from app.utils.tools import Mock, RunInThreadPool
from .config_service import ConfigService, APP_MODE
from app.utils.helper import b64_encode, get_value_in_list, phone_parser, uuid_v1_mc
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.http.async_http_client import AsyncTwilioHttpClient
from twilio.http.http_client import TwilioHttpClient
from datetime import datetime, timedelta, timezone
from twilio.rest.api.v2010.account.message import MessageInstance
from twilio.rest.api.v2010.account.call import CallInstance
from twilio.twiml.voice_response import VoiceResponse, Gather, Say,Record
from twilio.base.exceptions import TwilioRestException
import aiohttp
from aiohttp import BasicAuth
from twilio.rest.api.v2010.account import AccountInstance

@_service.MiniService(
    links=[_service.LinkDep(ProfileMiniService,build_follow_dep=True,to_async_verify=True)]
)
class TwilioAccountMiniService(_service.BaseMiniService,TwilioInterface):
    def __init__(self, configService: ConfigService,profileMiniService:ProfileMiniService[TwilioProfileModel]) -> None:
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)
        self.configService = configService
        self.mode:str = ...
        self.testUrl:str = ...
        self.twilio_url:str  = ...


    @property
    def logs_url(self):
        return self.twilio_url + "/status/logs"
        
    @property
    def partial_results_url(self):
        return self.twilio_url + "/status/partial-results"

    def gather_url(self):
        return self.twilio_url + '/gather'

    def build(self,build_state=-1):

        self.account_sid = self.depService.model.account_sid
        self.auth_token = self.depService.credentials.to_plain()['auth_token']
        try:
            
            client = Client(self.account_sid,self.auth_token)
            account = client.api.accounts(self.account_sid).fetch()
            if account.status !=  AccountInstance.Status.ACTIVE:
                raise _service.BuildFailureError
            
            if float(account.balance.fetch().balance)<0:
                _service.BuildSkipError
        
            self.mode = self.configService['TWILIO_MODE']
            self.testUrl = self.configService['TWILIO_TEST_URL']
            self.twilio_url = self.depService.model.twilio_url if self.mode == "prod" else self.testUrl
            http_client = AsyncTwilioHttpClient() if APP_MODE == ApplicationMode.server else TwilioHttpClient()
            self.client =  Client(self.account_sid,self.auth_token,http_client= http_client)
        
        except TwilioRestException as e:
                raise _service.BuildFailureError(e.details)
        except requests.exceptions.ConnectTimeout as e:
            raise _service.BuildFailureError()
        except Exception as e:
            raise _service.BuildFailureError(e.args)

    def verify_dependency(self):
        mode = self.configService.getenv('TWILIO_MODE','prod')
        if mode != 'prod':
            if self.configService.getenv('TWILIO_TEST_URL',None) == None:
                raise _service.BuildFailureError('TWILIO_TEST_URL must be set in non-prod mode')
            
        if self.depService.model.profile_state != ProfileState.ACTIVE:
            raise _service.BuildFailureError(f'Profile is not active {self.depService.model.profile_state.name} ')

    async def async_verify_dependency(self):
        async with self.depService.statusLock.reader:
            self.verify_dependency()
            return True

    async def verify_twilio_token(self, request: Request):
        twilio_signature = request.headers.get("X-Twilio-Signature", None)

        if not twilio_signature:
            raise HTTPException(
                status_code=400, detail='Twilio Signature not available')

        full_url = str(request.url)

        form_data = await request.form()
        params = {key: form_data[key] for key in form_data}

        validator = RequestValidator(self.auth_token)
        if not validator.validate(full_url, params, twilio_signature):
            raise HTTPException(
                status_code=403, detail="Invalid Twilio Signature")

    async def phone_lookup(self, phone_number: str, carrier=True, caller_name=False) -> tuple[int, dict]:
        phone_number, query = self._parse_phone_and_query(phone_number, carrier, caller_name)
        phone_number_instance = await self.client.lookups.phone_numbers(phone_number).fetch_async(type=query)
        return {
            'phone_number': phone_number_instance.phone_number,
            'country_code': phone_number_instance.country_code,
            'national_format': phone_number_instance.national_format,
            'carrier': phone_number_instance.carrier,
            'caller_name': phone_number_instance.caller_name,
            'adds_ons': phone_number_instance.add_ons,
        }

    async def fetch_balance(self):
        balance = await self.client.balance.fetch_async()
        return {
            'balance': balance.balance,
            'currency': balance.currency,
            'solution': balance._solution,
            'version':balance._version
        }

@_service.Service(
    is_manager=True,
    links=[_service.LinkDep(ProfileService,to_build=True,to_destroy=True,)]
)
class TwilioService(_service.BaseMiniServiceManager,TwilioInterface):
    
    def __init__(self, configService: ConfigService,mongooseService:MongooseService,vaultService:VaultService,profileService:ProfileService) -> None:
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.vaultService = vaultService
        self.profileService = profileService

        self.MiniServiceStore = _service.MiniServiceStore[TwilioAccountMiniService](self.__class__.__name__)
    
    async def pingService(self,infinite_wait:bool,data:dict,profile:str=None,as_manager:bool=False,**kwargs):
        if self.main == None:
            raise _service.ServiceNotAvailableError
        
        return super().pingService(infinite_wait,data,profile,as_manager,**kwargs)
    
    def verify_dependency(self):
        ...

    def build(self, build_state=...):
        main_set = False
        first_available = None
        self.main:TwilioAccountMiniService = None


        count = self.profileService.MiniServiceStore.filter_count(lambda p: p.model.__class__ == TwilioProfileModel)
        state_counter = self.StatusCounter(count)

        twilio_account_count = 0

        self.MiniServiceStore.clear()

        for id, p in self.profileService.MiniServiceStore:
            if p.model.__class__ == TwilioProfileModel:
                twilio_account_count+=1
                tams = TwilioAccountMiniService(self.configService, p)
                tams._builder(_service.BaseMiniService.QUIET_MINI_SERVICE, build_state, self.CONTAINER_LIFECYCLE_SCOPE)

                if tams.service_status in _service.ACCEPTABLE_STATES and first_available is None:
                    first_available = tams

                if tams.depService.model.main and tams.service_status in _service.ACCEPTABLE_STATES:
                    self.main = tams
                    main_set = True
                
                state_counter.count(tams)

                self.MiniServiceStore.add(tams)

        # If main is not set or not available, fallback to first available
        if not main_set or (self.main and self.main.service_status not in _service.ACCEPTABLE_STATES):
            self.main = first_available
        
        if self.main == None:
            raise _service.BuildFailureError
    
        super().build(state_counter)

    async def verify_twilio_token(self, request):
        return await self.main.verify_twilio_token(request)
        
    async def phone_lookup(self, phone_number, carrier=True, caller_name=False):
        return await self.main.phone_lookup(phone_number,carrier,caller_name)

@_service.AbstractServiceClass()
class BaseTwilioCommunication(_service.BaseService,ProfileEventInterface):
    def __init__(self, configService: ConfigService, twilioService: TwilioService,redisService:RedisService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService
        ProfileEventInterface.__init__(self,redisService)
        self.status_callback_type:str = ...
        
    def verify_dependency(self):
        if self.twilioService.service_status not in _service.ACCEPTABLE_STATES:
            raise _service.BuildFailureError
        
    async def async_verify_dependency(self):
        async with self.twilioService.statusLock.reader:
            return self.twilioService.service_status not in _service.ACCEPTABLE_STATES
        
    def set_url(self,status_callback,subject_id=None,twilio_tracking=None):
        url = status_callback + self.status_callback_type
        if subject_id!=None:
            url +=f'&subject_id={subject_id}'
        
        if twilio_tracking != None:
            url+=f'twilio_tracking_id={twilio_tracking}'
        return url

    @classmethod
    def response_extractor(cls, res) -> dict:
        ...

    @staticmethod
    def TwilioDynamicContext(func:Callable):

        @functools.wraps(func)
        async def async_wrapper(*args,**kwargs):
            return await func(*args,**kwargs)
        
        if APP_MODE == ApplicationMode.server:
            return async_wrapper

        return func


@_service.Service(
    endService=True,
    links=[_service.LinkDep(TwilioService,to_build=True,to_destroy=True,to_async_verify=True)]
)
class SMSService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService,redisService:RedisService):
        super().__init__(configService, twilioService,redisService)
        self.status_callback_type = '?type=sms'
    
    @classmethod
    def response_extractor(cls, message: MessageInstance) -> dict:
        return {
            'date_created': str(message.date_created),
            'date_sent': str(message.date_sent),
            'date_updated': str(message.date_updated),
            'price': str(message.price) if message.price is not None else None,
            'price_unit': message.price_unit,
            'status': message.status,
            'sid': message.sid,
            'message_service_sid': message.messaging_service_sid,
        }

    def __send_sms_sync__(self, messageData: dict, subject_id=None, twilio_tracking: list[str] = [],twilioProfile:str=None) -> MessageInstance:
        twilioProfile:TwilioAccountMiniService = self.twilioService.MiniServiceStore.get(twilioProfile)
        results = []
        events= []
        data = messageData.copy()
        for i,to in enumerate(messageData['to']):

            url = self.set_url(twilioProfile.logs_url,subject_id, get_value_in_list(twilio_tracking,i))
            now = datetime.now(timezone.utc).isoformat()
            data['to'] = to

            try:
                message = twilioProfile.client.messages.create(
                    provide_feedback=True, send_as_mms=True, 
                    status_callback=url,
                    **data)
                result = self.response_extractor(message)
                description = f'Sent request to third-party API'
                status = SMSStatusEnum.SENT.value
            
            except TwilioRestException as e:
                result = None
                description = f'Third Party Api could not process the request message: {e.msg} code:{e.code} '
                status = SMSStatusEnum.FAILED.value

            except Exception as e:
                result = None
                description = f'Failed to send the request'
                status = SMSStatusEnum.FAILED.value
            finally:
                if get_value_in_list(twilio_tracking,i) and isinstance(result, MessageInstance):
                    event = SMSEventORM.JSON(
                        event_id=uuid_v1_mc(),
                        sms_sid=result.sid,
                        direction='O',
                        current_event=status,
                        description=description,
                        date_event_received=now
                    )
                    events.append(event)
                results.append(result)

            return (results,(StreamConstant.TWILIO_EVENT_STREAM_SMS,events),{})
        
    async def __send_sms_async__(self, messageData: dict, subject_id=None, twilio_tracking: list[str] = [],twilioProfile:str=None) -> MessageInstance:
        twilioProfile:TwilioAccountMiniService = self.twilioService.MiniServiceStore.get(twilioProfile)
        results = []
        events= []
        data = messageData.copy()
        for i,to in enumerate(messageData['to']):

            url = self.set_url(twilioProfile.logs_url,subject_id, get_value_in_list(twilio_tracking,i))
            now = datetime.now(timezone.utc).isoformat()
            data['to'] = to

            try:
                message = twilioProfile.client.messages.create_async(
                    provide_feedback=True, send_as_mms=True, 
                    status_callback=url,
                    **data)
                result = self.response_extractor(message)
                description = f'Sent request to third-party API'
                status = SMSStatusEnum.SENT.value
            
            except TwilioRestException as e:
                result = None
                description = f'Third Party Api could not process the request message: {e.msg} code:{e.code} '
                status = SMSStatusEnum.FAILED.value

            except Exception as e:
                result = None
                description = f'Failed to send the request'
                status = SMSStatusEnum.FAILED.value
            finally:
                if get_value_in_list(twilio_tracking,i) and isinstance(result, MessageInstance):
                    event = SMSEventORM.JSON(
                        event_id=uuid_v1_mc(),
                        sms_sid=result.sid,
                        direction='O',
                        current_event=status,
                        description=description,
                        date_event_received=now
                    )
                    events.append(event)
                results.append(result)

            return (results,(StreamConstant.TWILIO_EVENT_STREAM_SMS,events),{})
    
    @Mock()
    async def send_otp(self, otpModel: OTPModel, body: str, background: bool = False,twilioProfile:str=None):
        twilioProfile:TwilioAccountMiniService = self.twilioService.MiniServiceStore.get(twilioProfile)
        status_callback = twilioProfile.logs_url + self.status_callback_type
        return await twilioProfile.client.messages.create_async(send_as_mms=True, provide_feedback=True, to=otpModel.to, status_callback=status_callback, from_=otpModel._from, body=body)

    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseTwilioCommunication.TwilioDynamicContext
    def send_custom_sms(self, messageData: dict, subject_id=None, twilio_tracking: list[str] = [],twilioProfile:str=None):
        if APP_MODE == ApplicationMode.server:
            return self.__send_sms_async__(messageData, subject_id, twilio_tracking,twilioProfile)
        return self.__send_sms_sync__(messageData, subject_id, twilio_tracking,twilioProfile)

    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseTwilioCommunication.TwilioDynamicContext
    def send_template_sms(self, message: dict, subject_id=None, twilio_tracking:list[str] = [],twilioProfile:str=None):
        if APP_MODE == ApplicationMode.server:
            return self.__send_sms_async__(message, subject_id, twilio_tracking,twilioProfile)
        return self.__send_sms_sync__(message, subject_id, twilio_tracking,twilioProfile)
    
    def get_message(self, to: str,twilioProfile:str):
        twilioProfile:TwilioAccountMiniService = self.twilioService.MiniServiceStore.get(twilioProfile)
        

@_service.Service(
    endService=True,
    links=[_service.LinkDep(TwilioService,to_build=True,to_destroy=True,to_async_verify=True)]
)
class CallService(BaseTwilioCommunication):
    status_callback_event = ['initiated', 'ringing', 'answered', 'completed','busy','failed','no-answer']

    def __init__(self, configService: ConfigService, twilioService: TwilioService,redisService:RedisService):
        super().__init__(configService, twilioService,redisService)

    @classmethod
    def response_extractor(cls, result: CallInstance):
        return {
            'caller_name': result.caller_name,
            'date_created': str(result.date_created) if result.date_created else None,
            'date_updated': str(result.date_updated) if result.date_updated else None,
            'end_time': str(result.end_time) if result.end_time else None,
            'duration': int(result.duration) if result.duration is not None else None,
            'answered_by': result.answered_by,
            'price': str(result.price) if result.price is not None else None,
            'price_unit': result.price_unit,
            'sid': result.sid,
            'direction': result.direction,
            'status': result.status,
            'queue_time':result.queue_time,
            'start_time': str(result.start_time) if result.start_time else None
        }

    @Mock()
    async def send_otp_voice_call(self, body: str, otp: OTPModel,twilio_profile:str):
        call = otp.model_dump(exclude=('content'))
        call['twiml'] = body
        result = await self.__create_call_async__(call,twilioProfile=twilio_profile)
        return result[0]

    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseTwilioCommunication.TwilioDynamicContext
    def send_custom_voice_call(self, body: str, voice: str, lang: str, loop: int, call: dict,subject_id=None,twilio_tracking:list[str]=None,twilio_profile:str=None):
        voiceResponse = VoiceResponse()
        voiceResponse.say(body, voice, loop, lang)
        call['twiml'] = voiceResponse
        if APP_MODE == ApplicationMode.server:
            return self.__create_call_async__(call,subject_id,twilio_tracking,twilio_profile)
        return self.__create_call_sync__(call,subject_id,twilio_tracking,twilio_profile)
        
    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseTwilioCommunication.TwilioDynamicContext
    def send_twiml_voice_call(self, url: str, call_details: dict,subject_id=None,twilio_tracking:list[str]=None,twilio_profile:str=None):
        call_details['url'] = url
        if APP_MODE == ApplicationMode.server:
            return self.__create_call_async__(call_details,subject_id,twilio_tracking,twilio_profile)
        return self.__create_call_sync__(call_details,subject_id,twilio_tracking,twilio_profile)

    @Mock()
    @ProfileEventInterface.EventWrapper
    @BaseTwilioCommunication.TwilioDynamicContext
    def send_template_voice_call(self, result: str, call_details: dict,subject_id=None,twilio_tracking:list[str]=None,twilio_profile:str=None):
        call_details['twiml'] = result
        if APP_MODE == ApplicationMode.server:
            return self.__create_call_async__(call_details,subject_id,twilio_tracking,twilio_profile)
        return self.__create_call_sync__(call_details,subject_id,twilio_tracking,twilio_profile)

    def __create_call_sync__(self, details: dict,subject_id:str=None,twilio_tracking:list[str]=[],twilioProfile:str=None):
   
        twilioProfile:TwilioAccountMiniService = self.twilioService.MiniServiceStore.get(twilioProfile)

        events= []
        results = []

        for i,to in enumerate(details['to']):
            now = datetime.now(timezone.utc).isoformat()
            url = self.set_url(twilioProfile.logs_url,subject_id,get_value_in_list(twilio_tracking,i))

            try:
                data = details.copy()
                data['to'] = to
                result = None
                result = twilioProfile.client.calls.create(**data, method='GET', status_callback_method='POST', status_callback=url, status_callback_event=CallService.status_callback_event)
                result = self.response_extractor(result)
                description = f'Sent request to third-party API'
                status = CallStatusEnum.SENT.value
            except TwilioRestException as e:
                result = None
                description = f'Third Party Api could not process the request message: {e.msg} code:{e.code} '
                status = SMSStatusEnum.FAILED.value

            except Exception as e:
                result=None
                description = f'Failed to send the request'
                status =CallStatusEnum.FAILED.value
            finally:
            
                if get_value_in_list(twilio_tracking,i) and isinstance(result,CallInstance):
                    
                    event = CallEventORM.JSON(event_id=str(uuid_v1_mc()),call_sid =result.sid ,call_id=twilio_tracking[i],direction='O',current_event=status,city=None,country=None,state=None,
                                            date_event_received=now, description=description)
                    events.append(event)
                results.append(result)
        return (results,(StreamConstant.TWILIO_EVENT_STREAM_CALL,events),{})

    async def __create_call_async__(self, details: dict,subject_id:str=None,twilio_tracking:list[str]=[],twilioProfile:str=None):
   
        twilioProfile:TwilioAccountMiniService = self.twilioService.MiniServiceStore.get(twilioProfile)

        events= []
        results = []

        for i,to in enumerate(details['to']):
            now = datetime.now(timezone.utc).isoformat()
            url = self.set_url(twilioProfile.logs_url,subject_id,get_value_in_list(twilio_tracking,i))

            try:
                data = details.copy()
                data['to'] = to
                result = None
                result = await twilioProfile.client.calls.create_async(**data, method='GET', status_callback_method='POST', status_callback=url, status_callback_event=CallService.status_callback_event)
                result = self.response_extractor(result)
                description = f'Sent request to third-party API'
                status = CallStatusEnum.SENT.value
            except TwilioRestException as e:
                result = None
                description = f'Third Party Api could not process the request message: {e.msg} code:{e.code} '
                status = SMSStatusEnum.FAILED.value

            except Exception as e:
                result=None
                description = f'Failed to send the request'
                status =CallStatusEnum.FAILED.value
            finally:
            
                if get_value_in_list(twilio_tracking,i) and isinstance(result,CallInstance):
                    
                    event = CallEventORM.JSON(event_id=str(uuid_v1_mc()),call_sid =result.sid ,call_id=twilio_tracking[i],direction='O',current_event=status,city=None,country=None,state=None,
                                            date_event_received=now, description=description)
                    events.append(event)
                results.append(result)
        return (results,(StreamConstant.TWILIO_EVENT_STREAM_CALL,events),{})
                
    def update_voice_call(self):
        ...

    def gather_dtmf(self, otpModel: GatherDtmfOTPModel,subject_id:str,request_id:str,twilioProfile:TwilioAccountMiniService):
        
        otp = otpModel.otp
        service = otpModel.service if otpModel.service else '-1'
        config = otpModel.content.model_dump(exclude={'instruction'})
        response = VoiceResponse()
        action_url = twilioProfile.gather_url+f'/dtmf'+f'?otp={otp}&return_url=-1&subject_id={subject_id}&hangup=true&request_id={request_id}&maxDigits={otpModel.content.numDigits}'
        gather = Gather(action=action_url, method='GET',input='dtmf',**config)

        self._add_instruction_when_gather(otpModel, service, response, gather,'dtmf')

        return response

    def _add_instruction_when_gather(self, otpModel:GatherOTPBaseModel, service:str, response:VoiceResponse, gather:Gather,input_type:Literal['dtmf','speech']):
        model_instruction = otpModel.instruction
        
        if model_instruction.add_instructions:
            for instruction in model_instruction.add_instructions:
                type_,value = instruction.type,instruction.value
                if type_ == 'say':
                    gather.say(message=value,language=otpModel.content.language)
                elif type_ == 'play':
                    gather.play(url=value)
                elif type_ == 'pause':
                    gather.pause(length=value)

        if not model_instruction.remove_base_instruction:
            base_instructions = f"Hi, please {'say the phrase provided' if input_type == 'speech' else 'enter the digits of your OTP'} for the service {service}."
            gather.say(message=base_instructions,language=otpModel.content.language)

        if model_instruction.add_finish_key_phrase:
            base_instructions = f"Press {otpModel.content.finishOnKey} when finished {'saying the otp phrase'if input_type == 'dtmf' else 'entered the digits.'}"
            gather.say(message=base_instructions,language=otpModel.content.language)

        response.append(gather)
        if model_instruction.no_input_instruction:
            say = Say(message=model_instruction.no_input_instruction,language=otpModel.content.language)
        else:
            say = Say(message='We could not verify the otp at the given please retry later',language=otpModel.content.language)
            
        response.append(say)
    
    def gather_speech(self,otpModel:GatherSpeechOTPModel,subject_id:str,request_id:str,twilioProfile:TwilioAccountMiniService):
        otp = otpModel.otp
        service = otpModel.service if otpModel.service else '-1'
        config = otpModel.content.model_dump(exclude={'instruction'})
        config['partialResultCallback'] = twilioProfile.partial_results_url
        config['partialResultCallbackMethod'] = 'POST'

        response = VoiceResponse()

        action_url = twilioProfile.gather_url+'/speech'+f'?otp={otp}&return_url=-1&subject_id={subject_id}&hangup=true&request_id={request_id}'
        gather = Gather(action=action_url, method='GET',input='speech',**config)

        self._add_instruction_when_gather(otpModel, service, response, gather)
        return response

class FaxService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)

class ConversationService(BaseTwilioCommunication):
    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)

    def build(self,build_state=-1):
        self.conversations = self.twilioService.client.conversations
