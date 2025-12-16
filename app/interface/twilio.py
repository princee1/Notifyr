from fastapi import Request
from app.definition._interface import Interface, IsInterface
from app.errors.twilio_error import TwilioPhoneNumberParseError
from app.utils.helper import phone_parser
from app.utils.validation import phone_number_validator


@IsInterface
class TwilioInterface(Interface):
    def parse_to_phone_format(self, phone_number: str) -> str:
        formatted_number = phone_parser(phone_number)

        if not phone_number_validator(formatted_number):
            raise TwilioPhoneNumberParseError(formatted_number)

        return formatted_number
   
    
    async def verify_twilio_token(self, request: Request):
        ...

    async def phone_lookup(self, phone_number: str,carrier=True,caller_name=False) -> tuple[int, dict]:
        ...

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
        pass

