import os
from typing import Any
from dotenv import load_dotenv, find_dotenv
from enum import Enum
from utils.fileIO import JSONFile
from definition import _service
import socket
from utils.helper import parseToBool


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

@_service.ServiceClass           
class ConfigService(_service.Service):
    
    def __init__(self) -> None:
        super().__init__()
        if not load_dotenv(ENV):
            path = find_dotenv(ENV)
            load_dotenv(path)
        self.config_json_app:JSONFile = None

    def parseToBool(value:str,default:bool | None = None):
        try:
            return parseToBool(value)
        except ValueError:
            ...
        except TypeError:
            ...
        
        return default
    
    @staticmethod
    def parseToInt(value:str, default:int | None = None,positive = True): # TODO need to add the build error level
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
            value = int(value)
            if positive:
                if value < 0:
                    raise ValueError
            return value
        except ValueError as e:
            pass
        except TypeError as e:
            pass
        except OverflowError as e:
            pass
        return default

    def build(self):
        self.set_config_value()
        self.verify()
    
    def getenv(self,key:str,default:Any=None)-> str | None | Any:
        val = os.getenv(key)
        if isinstance(val,str) and not val.strip()=="":
            return val
        
        return default

    def set_config_value(self):
        self.MODE = MODE.toMode(self.getenv('MODE'))
        self.PORT_PUBLIC = ConfigService.parseToInt(self.getenv("PORT_PUBLIC"),3000)
        self.PORT_PRIVATE = ConfigService.parseToInt(self.getenv("PORT_PRIVATE"),5000)
        self.LOG_LEVEL = ConfigService.parseToInt(self.getenv("LOG_LEVEL"), 2)
        self.HTTP_MODE = self.getenv("HTTP_MODE")
        self.HTTPS_CERTIFICATE=self.getenv("HTTPS_CERTIFICATE",'cert.pem')
        self.HTTPS_KEY =self.getenv("HTTPS_KEY",'key.pem')

        self.OAUTH_METHOD_RETRIEVER = self.getenv('OAUTH_METHOD_RETRIEVER','oauth_custom') #OAuthFlow | OAuthLib
        self.OAUTH_JSON_KEY_FILE = self.getenv('OAUTH_JSON_KEY_FILE')  # JSON key file
        self.OAUTH_TOKEN_DATA_FILE = self.getenv('OAUTH_DATA_FILE','mail_provider.tokens.json')
        self.OAUTH_CLIENT_ID=self.getenv('OAUTH_CLIENT_ID')
        self.OAUTH_CLIENT_SECRET=self.getenv('OAUTH_CLIENT_SECRET')
        self.OAUTH_OUTLOOK_TENANT_ID=self.getenv('OAUTH_TENANT_ID')


        self.SEND_MAIL_METHOD = self.getenv("SEND_MAIL_METHOD",'SMTP')
        self.SMTP_EMAIL_HOST = self.getenv("SMTP_EMAIL_HOST").upper()
        self.SMTP_EMAIL_PORT = ConfigService.parseToInt(self.getenv("SMTP_EMAIL_PORT"))
        self.SMTP_EMAIL = self.getenv("SMTP_EMAIL")
        self.SMTP_ADDR_SERVER  = self.getenv('SMTP_ADDR_SERVER')
        self.SMTP_PASS = self.getenv("SMTP_EMAIL_PASS")
        self.SMTP_EMAIL_CONN_METHOD= self.getenv("SMTP_EMAIL_CONN_METHOD")
        self.SMTP_EMAIL_LOG_LEVEL= ConfigService.parseToInt(self.getenv("SMTP_EMAIL_LOG_LEVEL"),0)

        # self.IMAP_EMAIL_HOST = self.getenv("IMAP_EMAIL_HOST").upper()
        # self.IMAP_EMAIL_PORT = ConfigService.parseToInt(self.getenv("IMAP_EMAIL_PORT"))
        # self.IMAP_EMAIL = self.getenv("IMAP_EMAIL")
        # self.IMAP_EMAIL_PASS = self.getenv("IMAP_EMAIL_PASS")
        # self.IMAP_EMAIL_CONN_METHOD= self.getenv("IMAP_EMAIL_CONN_METHOD")

        self.ASSET_LANG = self.getenv("ASSET_LANG")

        self.TWILIO_ACCOUNT_SID = self.getenv("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN= self.getenv("TWILIO_AUTH_TOKEN")
        self.TWILIO_NUMBER= self.getenv("TWILIO_NUMBER")
        
        self.JWT_SECRET_KEY = self.getenv("JWT_SECRET_KEY")
        self.JWT_ALGORITHM = self.getenv("JWT_ALGORITHM")
        self.API_KEY = self.getenv("API_KEY")
        self.ON_TOP_SECRET_KEY = self.getenv("ON_TOP_SECRET_KEY")
        self.API_ENCRYPT_TOKEN = self.getenv("API_ENCRYPT_TOKEN")
        self.API_EXPIRATION = ConfigService.parseToInt(self.getenv("API_EXPIRATION"), 3600000000000)
        self.AUTH_EXPIRATION = ConfigService.parseToInt(self.getenv("AUTH_EXPIRATION"), 3600000000000)

    def verify(self):
        if self.API_EXPIRATION < self.AUTH_EXPIRATION:
            # self.API_EXPIRATION = self.AUTH_EXPIRATION
            # raise _service.BuildWarningError("API_EXPIRATION cannot be less than AUTH_EXPIRATION")
            ...

    def __getitem__(self, key):
        return getattr(self, key)
    
    def get(self, key):
        return self.getenv(key)
    
    def load_configApp(self,config_file: str):
        config_json_app = JSONFile(config_file)
        config_file = config_file if config_json_app.exists else None
        #apps_data = config_json_app.data
        self.config_json_app = config_json_app
    
    def destroy(self):
        return super().destroy()
