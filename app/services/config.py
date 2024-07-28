import os
from dotenv import load_dotenv, find_dotenv
from enum import Enum
from . import _module
import socket

ENV = ".env"

class MODE(Enum):
    DEV_MODE = 'dev'
    PROD_MODE = 'prod'
    TEST_MODE = 'test'
    
    def toMode(val):
        match val:
            case MODE.DEV_MODE.value:
                return MODE.DEV_MODE
            case MODE.PROD_MODE.value:
                return MODE.PROD_MODE
            case MODE.TEST_MODE:
                return MODE.TEST_MODE.value
            case _:
                return MODE.DEV_MODE
    
    def modeToAddr(mode):
        match mode:
            case MODE.TEST_MODE:
                return "127.0.0.1"
            case _:
                return "127.0.0.1"

            
class ConfigService(_module.Module):
    
    def __init__(self) -> None:
        if not load_dotenv(ENV):
            path = find_dotenv(ENV)
            load_dotenv(path)
    
    
    def parseToInt(value:str, default:int | None = None): # TODO need to add the build error level
        """
        The function `parseToInt` attempts to convert a string to an integer and returns the integer
        value or a default value if conversion fails.
        
        :param value: The `value` parameter is a string that you want to parse into an integer
        :type value: str
        :param default: The `default` parameter in the `parseToInt` function is used to specify a
        default value that will be returned if the conversion of the input `value` to an integer fails.
        If no `default` value is provided, it defaults to `None`
        :type default: int | None
        :return: The `parseToInt` function is returning the integer value of the input `value` after
        converting it from a string. If the conversion is successful, it returns the integer value. If
        there is an error during the conversion (ValueError, TypeError, OverflowError), it returns the
        `default` value provided as a parameter. If no `default` value is provided, it returns `None`.
        """
        try:
            return int(value)
        except ValueError as e:
            pass
        except TypeError as e:
            pass
        except OverflowError as e:
            pass
        return default


    def build(self):
        self.MODE = MODE.toMode(os.getenv('MODE'))
        self.PORT_PUBLIC = ConfigService.parseToInt(os.getenv("PORT_PUBLIC"),3000)
        self.PORT_PRIVATE = ConfigService.parseToInt(os.getenv("PORT_PRIVATE"),5000)
        self.LOG_LEVEL = ConfigService.parseToInt(os.getenv("LOG_LEVEL"), 2)

        self.SMTP_EMAIL_HOST = os.getenv("SMTP_EMAIL_HOST").upper()
        self.SMTP_EMAIL_PORT = ConfigService.parseToInt(os.getenv("SMTP_EMAIL_PORT"))
        self.SMTP_EMAIL = os.getenv("SMTP_EMAIL")
        self.SMTP_EMAIL_PASS = os.getenv("SMTP_EMAIL_PASS")
        self.SMTP_EMAIL_CONN_METHOD= os.getenv("SMTP_EMAIL_CONN_METHOD")
        self.SMTP_EMAIL_LOG_LEVEL= ConfigService.parseToInt(os.getenv("SMTP_EMAIL_LOG_LEVEL"),0)

        self.IMAP_EMAIL_HOST = os.getenv("IMAP_EMAIL_HOST").upper()
        self.IMAP_EMAIL_PORT = ConfigService.parseToInt(os.getenv("IMAP_EMAIL_PORT"))
        self.IMAP_EMAIL = os.getenv("IMAP_EMAIL")
        self.IMAP_EMAIL_PASS = os.getenv("IMAP_EMAIL_PASS")
        self.IMAP_EMAIL_CONN_METHOD= os.getenv("IMAP_EMAIL_CONN_METHOD")
        
    def kill(self):
        return super().kill()
