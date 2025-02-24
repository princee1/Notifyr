from app.definition._error import BaseError



class CustomTwilioError(BaseError):
    ...


class TwilioPhoneNumberParseError(CustomTwilioError):
    ...