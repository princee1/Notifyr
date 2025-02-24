"""
https://www.youtube.com/watch?v=-AChTCBoTUM
"""

from typing import Annotated
from fastapi import HTTPException, Header, Request
from app.classes.template import SMSTemplate
from app.definition import _service
from app.models.otp_model import OTPModel
from app.services.assets_service import AssetService
from app.services.logger_service import LoggerService
from .config_service import ConfigService
from app.utils.helper import b64_encode
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from app.utils.validation import phone_number_validator
from app.classes.twilio import TwilioPhoneNumberParseError
from datetime import timedelta

letter_to_number = {
    'A': '2', 'B': '2', 'C': '2',
    'D': '3', 'E': '3', 'F': '3',
    'G': '4', 'H': '4', 'I': '4',
    'J': '5', 'K': '5', 'L': '5',
    'M': '6', 'N': '6', 'O': '6',
    'P': '7', 'Q': '7', 'R': '7', 'S': '7',
    'T': '8', 'U': '8', 'V': '8',
    'W': '9', 'X': '9', 'Y': '9', 'Z': '9'
}


@_service.ServiceClass
class TwilioService(_service.Service):
    def __init__(self, configService: ConfigService,) -> None:
        super().__init__()
        self.configService = configService

    def build(self):
        self.client = Client(self.configService.TWILIO_ACCOUNT_SID,
                             self.configService.TWILIO_AUTH_TOKEN)

    def parse_to_phone_format(self, phone_number: str) -> str:
        phone_number = phone_number.upper()
        converted_number = ''.join(letter_to_number.get(
            char, char) for char in phone_number)

        cleaned_number = ''.join(filter(str.isdigit, converted_number))

        if not cleaned_number.startswith('1'):
            cleaned_number = '1' + cleaned_number

        formatted_number = f"+{cleaned_number}"

        if not phone_number_validator(formatted_number):
            raise TwilioPhoneNumberParseError(formatted_number)

        return formatted_number


@_service.AbstractServiceClass
class BaseTwilioCommunication(_service.Service):
    def __init__(self, configService: ConfigService, twilioService: TwilioService, assetService: AssetService) -> None:
        super().__init__()
        self.configService = configService
        self.twilioService = twilioService
        self.assetService = assetService

    async def verify_twilio_token(self, request: Request):
        twilio_signature = request.headers.get("X-Twilio-Signature", "")

        full_url = str(request.url)

        form_data = await request.form()
        params = {key: form_data[key] for key in form_data}

        validator = RequestValidator(self.configService.TWILIO_AUTH_TOKEN)
        if not validator.validate(full_url, params, twilio_signature):
            raise HTTPException(
                status_code=403, detail="Invalid Twilio Signature")


@_service.ServiceClass
class SMSService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)
        self.status_callback = ...

    def send_otp(self, otpModel: OTPModel):
        company = otpModel.brand
        otp = otpModel.otp
        expiry = timedelta(seconds=otpModel.expiry).min
        match otpModel.type:
            case "verification":
                otp_phrase = f"You're verification code is: {otp}"

            case "login":
                otp_phrase = f"Your login OTP for {company} is {otp}. It will expire in {expiry} minutes. Do not share it."

            case "transaction":
                otp_phrase = f"Your OTP for confirming your transaction is {otp}. This code will expire in {expiry} minutes."

            case "mfa":
                otp_phrase = f"Use this OTP ({otp}) to verify your login for {company}. This code expires in {expiry} minutes."

            case "password_reset":
                otp_phrase = f"Use {otp} to reset your password for {company}. This code is valid for {expiry} minutes."

            case _:
                otp_phrase = f"Your OTP code is: {otp}. Do not share this code with anyone. It expires soon."

        return self.message.create(to=otpModel.to, status_callback=self.status_callback, from_=otpModel.from_, body=otp_phrase)

    def build(self):
        self.message = self.twilioService.client.messages

    def send_custom_sms(self, messageData: dict):
        return self.message.create(send_as_mms=True, status_callback=self.status_callback, **messageData)

    def send_template_sms(self, message):
        return self.message.create(send_as_mms=True, status_callback=self.status_callback, **message)


@_service.ServiceClass
class VoiceService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)
    pass


@_service.ServiceClass
class FaxService(BaseTwilioCommunication):

    def __init__(self, configService: ConfigService, twilioService: TwilioService):
        super().__init__(configService, twilioService)


