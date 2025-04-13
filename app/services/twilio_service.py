"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

import functools
from typing import Annotated, Callable, Coroutine
from fastapi import HTTPException, Header, Request
from app.classes.template import SMSTemplate
from app.definition import _service
from app.models.otp_model import GatherDtmfOTPModel, OTPModel
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
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from twilio.twiml.messaging_response import MessagingResponse
import aiohttp
import asyncio
from aiohttp import BasicAuth

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
class BaseTwilioCommunication(_service.Service):
    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService
        self.assetService = assetService

        mode = self.configService['TWILIO_MODE']
        self.twilio_url = self.configService.TWILIO_PROD_URL if mode == "prod" else self.configService.TWILIO_TEST_URL
        
        self.logs_url = self.twilio_url + "status/logs"
        self.partial_results_url = self.twilio_url + "status/partial-results"


    @staticmethod
    def parse_to_json(func: Callable):

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> dict | Coroutine:
            self: BaseTwilioCommunication = args[0]
            message: MessageInstance | Coroutine = func(*args, **kwargs)
            if asyncio.iscoroutine(message):
                @functools.wraps(func)
                async def callback():
                    r = await message
                    return self.response_extractor(r)
                return callback
            else:
                return self.response_extractor(message)
        return wrapper

    def response_extractor(self, res) -> dict:
        ...


@_service.ServiceClass
class SMSService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService):
        super().__init__(configService, twilioService, assetService)
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

    @BaseTwilioCommunication.parse_to_json
    def send_otp(self, otpModel: OTPModel, body: str, as_async: bool = False):
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(send_as_mms=True, provide_feedback=True, to=otpModel.to, status_callback=self.status_callback, from_=otpModel.from_, body=body)

    def build(self):
        self.messages = self.twilioService.client.messages

    @BaseTwilioCommunication.parse_to_json
    def send_custom_sms(self, messageData: dict, as_async: bool = False):
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(provide_feedback=True, send_as_mms=True, status_callback=self.status_callback, **messageData)

    @BaseTwilioCommunication.parse_to_json
    def send_template_sms(self, message, as_async: bool = False):
        as_async = False
        func = self.messages.create_async if as_async else self.messages.create
        return func(provide_feedback=True, send_as_mms=True, status_callback=self.status_callback, **message)

    def get_message(self, to: str):
        self.messages


@_service.ServiceClass
class CallService(BaseTwilioCommunication):
    status_callback_event = ['initiated', 'ringing', 'answered', 'completed']

    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService):
        super().__init__(configService, twilioService, assetService)
        self.status_callback = self.logs_url + '?type=call'
        self.gather_url = self.twilio_url + 'gather'

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
            'start_time': str(result.start_time) if result.start_time else None
        }

    @BaseTwilioCommunication.parse_to_json
    def send_otp_voice_call(self, body: str, otp: OTPModel,as_async: bool = False):
        call = {}
        call.update(otp.model_dump(exclude=('content')))
        call['twiml'] = body
        return self._create_call(call,as_async)

    @BaseTwilioCommunication.parse_to_json
    def send_custom_voice_call(self, body: str, voice: str, lang: str, loop: int, call: dict,as_async: bool = False):
        voiceResponse = VoiceResponse()
        voiceResponse.say(body, voice, loop, lang)
        call['twiml'] = voiceResponse
        return self._create_call(call,as_async)

    @BaseTwilioCommunication.parse_to_json
    def send_twiml_voice_call(self, url: str, call_details: dict,as_async: bool = False):
        call_details['url'] = url
        return self._create_call(call_details,as_async)

    @BaseTwilioCommunication.parse_to_json
    def send_template_voice_call(self, result: str, call_details: dict,as_async: bool = False):
        call_details['twiml'] = result
        return self._create_call(call_details,as_async)

    def _create_call(self, details: dict,as_async: bool = False):
        return self.calls.create(**details, method='GET', status_callback_method='POST', status_callback=self.status_callback, status_callback_event=CallService.status_callback_event)

    def update_voice_call(self):
        ...

    def gather_dtmf(self, otpModel: GatherDtmfOTPModel,subject_id:str,request_id:str):
        otp = otpModel.otp
        service = otpModel.service if otpModel.service else '-1'
        content = otpModel.content.model_dump(exclude={'remove_base_instruction','add_instructions','add_finish_key_phrase','no_input_instruction'})
        response = VoiceResponse()
        result_url= f'?service={service}&otp={otp}&return_url=-1&subject_id={subject_id}&contact=-1'
        gather = Gather(action=self.gather_url+f'/dtmf'+result_url, method='POST',input='dtmf',**content)
        
        if otpModel.content.add_instructions:
            for instruction in otpModel.content.add_instructions:
                type_,value = instruction.type,instruction.value
                if type_ == 'say':
                    gather.say(message=value,language=otpModel.content.language)
                elif type_ == 'play':
                    gather.play(url=value)
                elif type_ == 'pause':
                    gather.pause(length=value)

        if not otpModel.content.remove_base_instruction:
            base_instructions = f"Hi, please enter the digits of your OTP for the service {service}."
            gather.say(message=base_instructions,language=otpModel.content.language)

        if otpModel.content.add_finish_key_phrase:
            base_instructions = f"Press {otpModel.content.finishOnKey} when finished entered the digits."
            gather.say(message=base_instructions,language=otpModel.content.language)

        response.append(gather)
        if otpModel.content.no_input_instruction:
            say = Say(message=otpModel.content.no_input_instruction,language=otpModel.content.language)
        else:
            say = Say(message='We could not verify the otp at the given please retry later',language=otpModel.content.language)
            
        response.append(say)

        return response
    
    def gather_speech(self,subject_id:str,request_id:str):
        ...

@_service.ServiceClass
class FaxService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService):
        super().__init__(configService, twilioService, assetService)


class ConversationService(BaseTwilioCommunication):
    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService):
        super().__init__(configService, twilioService, assetService)

    def build(self):
        self.conversations = self.twilioService.client.conversations
