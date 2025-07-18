"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

import functools
from typing import Annotated, Callable, Coroutine, Literal
from fastapi import HTTPException, Header, Request
from app.classes.template import SMSTemplate
from app.definition import _service
from app.interface.redis_event import RedisEventInterface
from app.models.otp_model import GatherDtmfOTPModel, GatherOTPBaseModel, GatherSpeechOTPModel, OTPModel
from app.models.twilio_model import CallEventORM, CallStatusEnum, SMSEventORM, SMSStatusEnum
from app.services.assets_service import AssetService
from app.services.database_service import RedisService
from app.services.logger_service import LoggerService
from app.utils.constant import StreamConstant
from app.utils.tools import Mock
from .config_service import CeleryMode, ConfigService
from app.utils.helper import b64_encode, get_value_in_list, phone_parser, uuid_v1_mc
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from app.utils.validation import phone_number_validator
from app.errors.twilio_error import TwilioPhoneNumberParseError
from datetime import datetime, timedelta, timezone
from twilio.rest.api.v2010.account.message import MessageInstance
from twilio.rest.api.v2010.account.call import CallInstance
from twilio.twiml.voice_response import VoiceResponse, Gather, Say,Record
from twilio.twiml.messaging_response import MessagingResponse
from twilio.base.exceptions import TwilioRestException
import aiohttp
import asyncio
from aiohttp import BasicAuth
from twilio.rest.api.v2010.account import AccountInstance

@_service.Service
class TwilioService(_service.BaseService):
    def __init__(self, configService: ConfigService,) -> None:
        super().__init__()
        self.configService = configService
        self.SERVICE_ID = self.configService.getenv('TWILIO_SERVICE_ID')

    def build(self):
        self.client = Client(self.configService.TWILIO_ACCOUNT_SID,
                             self.configService.TWILIO_AUTH_TOKEN)
        try:
            account = self.client.api.accounts(self.configService.TWILIO_ACCOUNT_SID).fetch()
            if account.status !=  AccountInstance.Status.ACTIVE:
                raise _service.BuildFailureError
            
            if float(account.balance.fetch().balance)<0:
                _service.BuildSkipError
                
        except TwilioRestException as e:
                raise _service.BuildFailureError
    
    def verify_dependency(self):
        if not self.configService.TWILIO_ACCOUNT_SID or not self.configService.TWILIO_AUTH_TOKEN:
            raise _service.BuildFailureError
            
    def parse_to_phone_format(self, phone_number: str) -> str:
        formatted_number = phone_parser(phone_number)

        if not phone_number_validator(formatted_number):
            raise TwilioPhoneNumberParseError(formatted_number)

        return formatted_number

    async def verify_twilio_token(self, request: Request):
        twilio_signature = request.headers.get("X-Twilio-Signature", None)

        if not twilio_signature:
            raise HTTPException(
                status_code=400, detail='Twilio Signature not available')

        full_url = str(request.url)

        form_data = await request.form()
        params = {key: form_data[key] for key in form_data}

        validator = RequestValidator(self.configService.TWILIO_AUTH_TOKEN)
        if not validator.validate(full_url, params, twilio_signature):
            raise HTTPException(
                status_code=403, detail="Invalid Twilio Signature")

    async def update_env_variable(self, auth_token, refresh_token):

        response = ...
        status_code: int = ...

        return status_code

    async def async_phone_lookup(self, phone_number: str,carrier=True,caller_name=False) -> tuple[int, dict]:
        phone_number, query = self._parse_phone_and_query(phone_number, carrier, caller_name)    
        query = ','.join(query)

        account_sid = self.configService.TWILIO_ACCOUNT_SID
        auth_token = self.configService.TWILIO_AUTH_TOKEN
        basic_auth = BasicAuth(account_sid, auth_token)
        async with aiohttp.ClientSession(auth=basic_auth) as session:
            async with session.get(f'https://lookups.twilio.com/v1/PhoneNumbers/{phone_number}?Type={query}') as response:
                body = await response.json()
                status_code = response.status
                return status_code,body

    def _parse_phone_and_query(self, phone_number, carrier, caller_name):
        phone_number = self.parse_to_phone_format(phone_number)

        query = []
        if carrier:
            query.append('carrier')

        if caller_name:
            query.append('caller_name')

        # if adds_ons:
        #     query.append('add_ons')

        return phone_number,query

    def phone_lookup(self, phone_number: str, carrier=True, caller_name=False) -> tuple[int, dict]:
        phone_number, query = self._parse_phone_and_query(phone_number, carrier, caller_name)
        phone_number_instance = self.client.lookups.phone_numbers(phone_number).fetch(type=query)
        return {
            'phone_number': phone_number_instance.phone_number,
            'country_code': phone_number_instance.country_code,
            'national_format': phone_number_instance.national_format,
            'carrier': phone_number_instance.carrier,
            'caller_name': phone_number_instance.caller_name,
            'adds_ons': phone_number_instance.add_ons,
        }

@_service.AbstractServiceClass
class BaseTwilioCommunication(_service.BaseService,RedisEventInterface):
    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService,redisService:RedisService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService
        self.assetService = assetService
        RedisEventInterface.__init__(self,redisService)
        
        mode = self.configService['TWILIO_MODE']
        self.twilio_url = self.configService.TWILIO_PROD_URL if mode == "prod" else self.configService.TWILIO_TEST_URL
        
        self.logs_url = self.twilio_url + "/status/logs"
        self.partial_results_url = self.twilio_url + "/status/partial-results"

    def verify_dependency(self):
        if self.twilioService.service_status == _service.ServiceStatus.NOT_AVAILABLE:
            raise _service.BuildFailureError

        if self.redisService.service_status == _service.ServiceStatus.NOT_AVAILABLE:
            raise _service.BuildWarningError

    def set_url(self,subject_id=None,twilio_tracking=None):
        url = self.status_callback
        if subject_id!=None:
            url +=f'&subject_id={subject_id}'
        
        if twilio_tracking != None:
            url+=f'twilio_tracking_id={twilio_tracking}'
        return url

    @staticmethod
    def parse_to_json(pref:Literal['async','sync']=None,async_callback=None,sync_callback=None):

        def callback(func:Callable):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> dict:
                self: BaseTwilioCommunication = args[0]
                if asyncio.iscoroutinefunction(func):
                    message:CallInstance| MessageInstance | Coroutine = await func(*args, **kwargs)
                else:
                    message:CallInstance| MessageInstance | Coroutine = func(*args, **kwargs)
                if message== None:
                    return None
                
                if callable(async_callback):
                    await async_callback(self,*result[1],**result[2])
                    result = result[0]
                else:
                    if isinstance(result,tuple):
                        result = result[0]

                return self.response_extractor(message)

            @functools.wraps(func)
            def sync_wrapper(*args,**kwargs):
                self: BaseTwilioCommunication = args[0]

                message:CallInstance| MessageInstance | Coroutine = func(*args, **kwargs)
                if message== None:
                    return None
                
                if callable(sync_callback):
                    sync_callback(self,*result[1],**result[2])
                    result = result[0]
                else:
                    if isinstance(result,tuple):
                        result = result[0]
                return self.response_extractor(message)

            if ConfigService._celery_env == CeleryMode.worker:
                return sync_wrapper
            
            if pref =='async':
                return async_wrapper

            if pref == 'sync':
                return sync_wrapper 
                    
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        
        return callback
    
    def response_extractor(self, res) -> dict:
        ...


@_service.Service
class SMSService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService,redisService:RedisService):
        super().__init__(configService, twilioService, assetService,redisService)
        self.status_callback = self.logs_url + '?type=sms'

    def response_extractor(self, message: MessageInstance) -> dict:
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

    @BaseTwilioCommunication.parse_to_json()
    async def send_otp(self, otpModel: OTPModel, body: str, as_async: bool = False):
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(send_as_mms=True, provide_feedback=True, to=otpModel.to, status_callback=self.status_callback, from_=otpModel.from_, body=body)

    def build(self):
        self.messages = self.twilioService.client.messages

    def _send_sms(self, messageData: dict, subject_id=None, twilio_tracking: list[str] = []) -> MessageInstance:
        
        results = []
        events= []
        for i,to in enumerate(messageData['to']):

            url = self.set_url(subject_id, get_value_in_list(twilio_tracking,i))
            now = datetime.now(timezone.utc).isoformat()

            data = messageData.copy()
            data['to'] = to

            try:
                #if self.configService.celery_env == CeleryMode.worker:
                result = self.messages.create(provide_feedback=True, send_as_mms=True, status_callback=url, **data)
                # else:
                #     result = self.messages.create_async(provide_feedback=True, send_as_mms=True, status_callback=url, **messageData)
                #     result = await result
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
        
    @BaseTwilioCommunication.parse_to_json('async',*RedisEventInterface.redis_event_callback)
    def send_custom_sms(self, messageData: dict, subject_id=None, twilio_tracking: list[str] = []):
        return self._send_sms(messageData, subject_id, twilio_tracking)

    @BaseTwilioCommunication.parse_to_json('async',*RedisEventInterface.redis_event_callback)
    async def send_template_sms(self, message: dict, subject_id=None, twilio_tracking:list[str] = []):
        return self._send_sms(message, subject_id, twilio_tracking)

    def get_message(self, to: str):
        self.messages


@_service.Service
class CallService(BaseTwilioCommunication):
    status_callback_event = ['initiated', 'ringing', 'answered', 'completed','busy','failed','no-answer']

    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService,redisService:RedisService):
        super().__init__(configService, twilioService, assetService,redisService)
        self.status_callback = self.logs_url + '?type=call'
        self.gather_url = self.twilio_url + '/gather'

    def build(self):
        self.call = self.twilioService.client

    def fetch_balance(self):
        balance = self.call.balance.fetch()
        return {
            'balance': balance.balance,
            'currency': balance.currency,
            'solution': balance._solution,
        }

    @property
    def calls(self):
        return self.call.calls

    def response_extractor(self, result: CallInstance):
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

    @BaseTwilioCommunication.parse_to_json('async')
    def send_otp_voice_call(self, body: str, otp: OTPModel):
        call = {}
        call.update(otp.model_dump(exclude=('content')))
        call['twiml'] = body
        return self._create_call(call)

    @BaseTwilioCommunication.parse_to_json(('async',*RedisEventInterface.redis_event_callback))
    def send_custom_voice_call(self, body: str, voice: str, lang: str, loop: int, call: dict,subject_id=None,twilio_tracking:list[str]=None):
        voiceResponse = VoiceResponse()
        voiceResponse.say(body, voice, loop, lang)
        call['twiml'] = voiceResponse
        return self._create_call(call,subject_id,twilio_tracking)

    @BaseTwilioCommunication.parse_to_json('async',*RedisEventInterface.redis_event_callback)
    def send_twiml_voice_call(self, url: str, call_details: dict,subject_id=None,twilio_tracking:list[str]=None):
        call_details['url'] = url
        return self._create_call(call_details,subject_id,twilio_tracking)

    @BaseTwilioCommunication.parse_to_json('async',*RedisEventInterface.redis_event_callback)
    def send_template_voice_call(self, result: str, call_details: dict,subject_id=None,twilio_tracking:list[str]=None):
        call_details['twiml'] = result
        return self._create_call(call_details,subject_id,twilio_tracking)

    def _create_call(self, details: dict,subject_id:str=None,twilio_tracking:list[str]=[]):
   
        
        events= []
        results = []

        for i,to in enumerate(details['to']):
            now = datetime.now(timezone.utc).isoformat()
            url = self.set_url(subject_id,get_value_in_list(twilio_tracking,i))

            try:
                data = details.copy()
                data['to'] = to
                result = None
                result = self.calls.create(**data, method='GET', status_callback_method='POST', status_callback=url, status_callback_event=CallService.status_callback_event)

                # if self.configService.celery_env == CeleryMode.worker:
                #     result = self.calls.create(**details, method='GET', status_callback_method='POST', status_callback=url, status_callback_event=CallService.status_callback_event)
                # else:
                #     result = self.calls.create_async(**details, method='GET', status_callback_method='POST', status_callback=url, status_callback_event=CallService.status_callback_event)
                #     result = await result
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

    def gather_dtmf(self, otpModel: GatherDtmfOTPModel,subject_id:str,request_id:str):
        otp = otpModel.otp
        service = otpModel.service if otpModel.service else '-1'
        config = otpModel.content.model_dump(exclude={'instruction'})
        response = VoiceResponse()
        action_url = self.gather_url+f'/dtmf'+f'?otp={otp}&return_url=-1&subject_id={subject_id}&hangup=true&request_id={request_id}&maxDigits={otpModel.content.numDigits}'
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
    
    def gather_speech(self,otpModel:GatherSpeechOTPModel,subject_id:str,request_id:str):
        otp = otpModel.otp
        service = otpModel.service if otpModel.service else '-1'
        config = otpModel.content.model_dump(exclude={'instruction'})
        config['partialResultCallback'] = self.partial_results_url
        config['partialResultCallbackMethod'] = 'POST'

        response = VoiceResponse()

        action_url = self.gather_url+'/speech'+f'?otp={otp}&return_url=-1&subject_id={subject_id}&hangup=true&request_id={request_id}'
        gather = Gather(action=action_url, method='GET',input='speech',**config)

        self._add_instruction_when_gather(otpModel, service, response, gather)
        return response




class FaxService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService):
        super().__init__(configService, twilioService, assetService)


class ConversationService(BaseTwilioCommunication):
    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService):
        super().__init__(configService, twilioService, assetService)

    def build(self):
        self.conversations = self.twilioService.client.conversations
