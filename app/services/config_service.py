import os
from typing import Any, TypedDict
from typing_extensions import Literal
from dotenv import load_dotenv, find_dotenv
from enum import Enum
from app.utils.fileIO import JSONFile
from app.definition import _service
import socket
from app.utils.helper import parseToBool
import shutil
import sys


ENV = ".env"
CELERY_EXE_PATH = shutil.which("celery").replace(".EXE", "")

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
            case MODE.TEST_MODE.value:
                return MODE.TEST_MODE
            case _:
                return MODE.DEV_MODE

    def modeToAddr(mode):
        match mode:
            case MODE.DEV_MODE:
                return "127.0.0.1"
            case _:
                return "127.0.0.1"

class CeleryMode(Enum):
    flower = 'flower'
    worker = 'worker'
    beat = 'beat'
    none = 'none'
    purge = 'purge'

class ServerConfig(TypedDict):
    host: str
    port: int
    reload: bool
    team: Literal['team','solo']
    workers: int
    log_level: Literal["critical", "error",
                       "warning", "info", "debug", "trace"]

CeleryEnv = Literal['flower', 'worker', 'beat', 'none','purge']

_celery_env_ = CeleryMode.none
@_service.Service()
class ConfigService(_service.BaseService):
        
    if sys.argv[0] == CELERY_EXE_PATH:
        global _celery_env_
        _celery_env_ = CeleryMode._member_map_[sys.argv[3]]

    _celery_env = _celery_env_

    @property
    def celery_env(self) -> CeleryMode:
        return self._celery_env

    def set_celery_env(env: CeleryEnv):
        ConfigService._celery_env = CeleryMode._member_map_[env]

    def __init__(self) -> None:
        super().__init__()
        if not load_dotenv(ENV, verbose=True):
            path = find_dotenv(ENV)
            load_dotenv(path)
        self.server_config = None
        self.app_name = None

    def relative_path(self, path):
        return self.BASE_DIR + path

    @staticmethod
    def parseToBool(value: str, default: bool | None = None):
        try:
            return parseToBool(value)
        except ValueError:
            ...
        except TypeError:
            ...
        return bool(default)

    @staticmethod
    # TODO need to add the build error level
    def parseToInt(value: str, default: int | None = None, positive=True):
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

    def build(self,build_state=-1):
        self.set_config_value()
        self.verify()

    def getenv(self, key: str, default: Any = None) -> str | None | Any:
        val = os.getenv(key)
        if val is not None:
            val = val.strip()
            val = val.replace('"', "")
        if isinstance(val, str) and not val == "":
            return val
        return default
    

    def get_value_from_mode(self,dev_value,prod_value,test_value=None,):
        match self.MODE:
            case MODE.DEV_MODE:
                return dev_value
            case MODE.PROD_MODE:
                return prod_value

            case MODE.TEST_MODE:
                return test_value
            case _:
                return dev_value

    def set_config_value(self):

        self.INSTANCE_ID = ConfigService.parseToInt(self.getenv('INSTANCE_ID', '0'))
        self.PROCESS_PID = str(os.getpid())
        self.PARENT_PID = str(os.getppid())
        self.MODE = MODE.toMode(self.getenv('MODE','dev').lower())

        self.HOSTNAME = self.getenv('HOSTNAME',socket.getfqdn())
        
        self.BASE_DIR = self.getenv("BASE_DIR", './')
        self.ASSET_DIR = self.getenv("ASSETS_DIR", 'assets/')
        
        self.SECURITY_FLAG: bool = ConfigService.parseToBool(self.getenv('SECURITY_FLAG'), True)

        self.HTTP_MODE = self.getenv("HTTP_MODE",'HTTP')
        self.HTTPS_CERTIFICATE = self.getenv("HTTPS_CERTIFICATE", 'cert.pem')
        self.HTTPS_KEY = self.getenv("HTTPS_KEY", 'key.pem')

        self.NGROK_DOMAIN = self.getenv("NGROK_DOMAIN", None)

        self.OAUTH_METHOD_RETRIEVER = self.getenv('OAUTH_METHOD_RETRIEVER', 'oauth_custom')  # OAuthFlow | OAuthLib
        self.OAUTH_JSON_KEY_FILE = self.getenv('OAUTH_JSON_KEY_FILE')  # JSON key file
        self.OAUTH_TOKEN_DATA_FILE = self.getenv('OAUTH_DATA_FILE', 'mail_provider.tokens.json')
        self.OAUTH_CLIENT_ID = self.getenv('OAUTH_CLIENT_ID')
        self.OAUTH_CLIENT_SECRET = self.getenv('OAUTH_CLIENT_SECRET')
        self.OAUTH_OUTLOOK_TENANT_ID = self.getenv('OAUTH_TENANT_ID')
        
        self.SEND_MAIL_METHOD = self.getenv("SEND_MAIL_METHOD", 'SMTP')
        self.SMTP_EMAIL_HOST = self.getenv("SMTP_EMAIL_HOST").upper()
        self.SMTP_EMAIL_PORT = ConfigService.parseToInt(self.getenv("SMTP_EMAIL_PORT"))
        self.SMTP_EMAIL = self.getenv("SMTP_EMAIL")
        self.SMTP_ADDR_SERVER = self.getenv('SMTP_ADDR_SERVER')
        self.SMTP_PASS = self.getenv("SMTP_EMAIL_PASS")
        self.SMTP_EMAIL_CONN_METHOD = self.getenv("SMTP_EMAIL_CONN_METHOD",'tls')
        self.SMTP_EMAIL_LOG_LEVEL = ConfigService.parseToInt(self.getenv("SMTP_EMAIL_LOG_LEVEL"), 0)

        self.READ_MAIL_METHOD = self.getenv("READ_MAIL_METHOD", 'IMAP')
        self.IMAP_EMAIL_HOST = self.getenv("IMAP_EMAIL_HOST", self.SMTP_EMAIL_HOST).upper()
        self.IMAP_EMAIL_PORT = ConfigService.parseToInt(self.getenv("IMAP_EMAIL_PORT"))
        self.IMAP_EMAIL = self.getenv("IMAP_EMAIL", self.SMTP_EMAIL)
        self.IMAP_ADDR_SERVER = self.getenv('IMAP_ADDR_SERVER')
        self.IMAP_PASS = self.getenv("IMAP_EMAIL_PASS", self.SMTP_PASS)
        self.IMAP_EMAIL_CONN_METHOD = self.getenv("IMAP_EMAIL_CONN_METHOD", self.SMTP_EMAIL_CONN_METHOD)
        self.IMAP_EMAIL_LOG_LEVEL = ConfigService.parseToInt(self.getenv("IMAP_EMAIL_LOG_LEVEL"), self.SMTP_EMAIL_LOG_LEVEL)

        self.TWILIO_ACCOUNT_SID = self.getenv("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN = self.getenv("TWILIO_AUTH_TOKEN")
        self.TWILIO_NUMBER = self.getenv("TWILIO_NUMBER")
        self.TWILIO_PROD_URL = self.getenv("TWILIO_PROD_URL", None)
        self.TWILIO_TEST_URL = self.getenv("TWILIO_TEST_URL", None)

        self.ADMIN_KEY = self.getenv("ADMIN_KEY")
        self.API_KEY = self.getenv("API_KEY")
        

        # HASHI CORP VAULT CONFIG #

        self.VAULT_ADDR = self.getenv('VAULT_ADDR','http://127.0.0.1:8200' if self.MODE == MODE.DEV_MODE else 'http://vault:8200')

        # MONGODB CONFIG #

        self.MONGO_HOST = self.getenv('MONGO_HOST','localhost' if self.MODE == MODE.DEV_MODE else 'mongodb')

        # SETTING DB CONFIG #
        self.SETTING_DB_URL = self.getenv("SETTING_DB_URL","http://localhost:3000" if self.MODE == MODE.DEV_MODE else "http://settingdb:3000")

        # REDIS CONFIG #

        self.REDIS_URL = self.getenv("REDIS_URL","redis://localhost" if self.MODE == MODE.DEV_MODE else "redis://redis")

        # SLOW API CONFIG #

        self.SLOW_API_REDIS_URL = self.REDIS_URL + self.getenv("SLOW_API_STORAGE_URL", '/1')

        # POSTGRES DB CONFIG #

        self.POSTGRES_HOST = self.getenv('POSTGRES_HOST','localhost' if self.MODE == MODE.DEV_MODE else 'postgres')

        # CELERY CONFIG #

        self.CELERY_MESSAGE_BROKER_URL = self.REDIS_URL + self.getenv("CELERY_MESSAGE_BROKER_URL", '/0')
        self.CELERY_BACKEND_URL = self.REDIS_URL + self.getenv("CELERY_BACKEND_URL", '/0')
        self.REDBEAT_REDIS_URL = self.REDIS_URL + self.getenv("REDBEAT_REDIS_URL", self.CELERY_MESSAGE_BROKER_URL)

        self.CELERY_RESULT_EXPIRES = ConfigService.parseToInt(self.getenv("CELERY_RESULT_EXPIRES"), 60*60*24)
        self.CELERY_WORKERS_COUNT = self.getenv("CELERY_WORKERS_COUNT", 1)        


    def verify(self):

            # self.API_EXPIRATION = self.AUTH_EXPIRATION
            # raise _service.BuildWarningError("API_EXPIRATION cannot be less than AUTH_EXPIRATION")
            ...

    def __getitem__(self, key):
        try:
            result = getattr(self, key)
        except AttributeError:
            result = os.getenv(key)

        return result

    def get(self, key):
        return self.getenv(key)

    def destroy(self,destroy_state=-1):
        return super().destroy()

    def set_server_config(self, config):
        self.server_config = ServerConfig(host=config.host, port=config.port,
                                          reload=config.reload, workers=config.workers, log_level=config.log_level,
                                          team=config.team)
    @property
    def pool(self):
        if self.server_config['team'] == 'solo':
            return self.server_config['workers'] > 1
        else:
            return True
