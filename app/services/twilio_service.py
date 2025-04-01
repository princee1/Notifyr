"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

import functools
from typing import Annotated, Callable, Coroutine
from fastapi import HTTPException, Header, Request
from app.classes.template import SMSTemplate
from app.definition import _service
from app.models.otp_model import OTPModel
from app.services.assets_service import AssetService
from app.services.logger_service import LoggerService
from .config_service import ConfigService
from app.utils.helper import b64_encode, phone_parser
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from app.utils.validation import phone_number_validator
from app.errors.twilio_error import TwilioPhoneNumberParseError
from datetime import timedelta
from twilio.rest.api.v2010.account.message import MessageInstance
from twilio.rest.api.v2010.account.call import CallInstance
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
import asyncio



@_service.ServiceClass
class TwilioService(_service.Service):
    def __init__(self, configService: ConfigService,) -> None:
        super().__init__()
        self.configService = configService
        self.SERVICE_ID = self.configService.getenv('TWILIO_SERVICE_ID')

    def build(self):
        self.client = Client(self.configService.TWILIO_ACCOUNT_SID,
                             self.configService.TWILIO_AUTH_TOKEN)

    def parse_to_phone_format(self, phone_number: str) -> str:
        formatted_number=phone_parser(phone_number)

        if not phone_number_validator(formatted_number):
            raise TwilioPhoneNumberParseError(formatted_number)

        return formatted_number
    
    async def verify_twilio_token(self, request: Request):
        twilio_signature = request.headers.get("X-Twilio-Signature", None)

        if not twilio_signature:
            raise HTTPException(status_code=400,detail='Twilio Signature not available')

        full_url = str(request.url)

        form_data = await request.form()
        params = {key: form_data[key] for key in form_data}

        validator = RequestValidator(self.configService.TWILIO_AUTH_TOKEN)
        if not validator.validate(full_url, params, twilio_signature):
            raise HTTPException(
                status_code=403, detail="Invalid Twilio Signature")

    async def update_env_variable(self,auth_token,refresh_token):
        
        response = ...
        status_code:int = ...
        
        return status_code


@_service.AbstractServiceClass
class BaseTwilioCommunication(_service.Service):
    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService
        self.assetService = assetService

        mode = self.configService['TWILIO_MODE']
        self.url =  self.configService.TWILIO_PROD_URL if mode == "prod" else self.configService.TWILIO_TEST_URL
        self.url+="/auth-logs"
        
    @staticmethod
    def parse_message_to_json(func:Callable):

        @functools.wraps(func)
        def wrapper(*args,**kwargs) -> dict | Coroutine:
            self:BaseTwilioCommunication = args[0]
            message:MessageInstance|Coroutine = func(*args,**kwargs)
            if asyncio.iscoroutine(message): 
                @functools.wraps(func)
                async def callback():
                    r = await message
                    return self.response_extractor(r)
                return callback
            else:
                return self.response_extractor(message)
        return wrapper

    def response_extractor(self,res)->dict:
        ...
   


@_service.ServiceClass
class SMSService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService,assetService:AssetService):
        super().__init__(configService, twilioService,assetService)
        self.status_callback = self.url + '?type=sms'

    def response_extractor(self,message:MessageInstance)->dict:
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

    @BaseTwilioCommunication.parse_message_to_json
    def send_otp(self, otpModel: OTPModel,body:str,as_async:bool = False): #TODO otp template
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(send_as_mms=True,provide_feedback=True,to=otpModel.to, status_callback=self.status_callback, from_=otpModel.from_, body=body)
     
    def build(self):
        self.messages = self.twilioService.client.messages

    @BaseTwilioCommunication.parse_message_to_json
    def send_custom_sms(self, messageData: dict,as_async:bool = False):
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(provide_feedback=True,send_as_mms=True, status_callback=self.status_callback, **messageData)

    @BaseTwilioCommunication.parse_message_to_json
    def send_template_sms(self, message,as_async:bool = False):
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(provide_feedback=True,send_as_mms=True, status_callback=self.status_callback, **message)

    def get_message(self,to:str):
        self.messages

@_service.ServiceClass
class VoiceService(BaseTwilioCommunication):
    status_callback_event = ['initiated', 'ringing', 'answered', 'completed']

    def __init__(self, configService: ConfigService, twilioService: TwilioService,assetService: AssetService):
        super().__init__(configService, twilioService,assetService)
        self.status_callback = self.url + '?type=call'

    
    def build(self):
        self.call = self.twilioService.client

    def fetch_balance(self):
        balance = self.call.balance.fetch()
        return {
            'balance':balance.balance,
            'currency':balance.currency
        }

    @property
    def calls(self):
        return self.call.calls
    
    @staticmethod
    def parse_call_to_json(func:Callable):

        @functools.wraps(func)
        def wrapper(*args,**kwargs):
            result:CallInstance = func(*args,**kwargs)
            return {
                'caller_name':result.caller_name,
                'date_created':result.date_created,
                'date_updated':result.date_updated,
                'end_time':result.end_time,
                'duration':result.duration,
                'answered_by':result.answered_by,
                'price':result.price,
                'price_unit':result.price_unit,
                'sid':result.sid,
                'direction':result.direction,
                'status':result.status,
                'start_time':result.start_time
            }
        return wrapper

    def send_otp_voice_call(self):
        ...

    @parse_call_to_json
    def send_custom_voice_call(self,body:str,call:dict):
        voice = VoiceResponse()
        voice.say(body)
        call['twiml']= voice
        return self._create_call(call)
    
    @parse_call_to_json
    def send_twiml_voice_call(self, url:str,call_details:dict):
        call_details['url']= url
        return self._create_call(call_details)
        
    @parse_call_to_json
    def send_template_voice_call(self,result:str,call_details:dict):
        voiceRes = self._to_twiml(result)
        call_details['twiml'] = voiceRes
        return self._create_call(call_details)
    
    def _create_call(self, details:dict):
        return self.calls.create(**details,method='GET',status_callback_method='POST',status_callback=self.status_callback,status_callback_event=VoiceService.status_callback_event)

    def update_voice_call(self):
        ...

    def _to_twiml(self,result:str):
        return ...
        
@_service.ServiceClass
class FaxService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService,assetService: AssetService):
        super().__init__(configService, twilioService,assetService)

class ConversationService(BaseTwilioCommunication):
    def __init__(self, configService: ConfigService, twilioService: TwilioService,assetService: AssetService):
        super().__init__(configService, twilioService,assetService)

    
    def build(self):
        self.conversations = self.twilioService.client.conversations
