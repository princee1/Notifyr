import os
from typing import Any, TypedDict
from typing_extensions import Literal
from dotenv import load_dotenv, find_dotenv
from enum import Enum
from app.errors.service_error import BuildAbortError, BuildWarningError
from app.utils.constant import RedisConstant
from app.utils.fileIO import JSONFile
from app.definition import _service
import socket
from app.utils.globals import DIRECTORY_SEPARATOR
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


class AssetMode(Enum):
    s3 = 's3'
    github = 'github'
    local = 'local'
    ftp = 'ftp'


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
    
    @staticmethod # TODO need to add the build error level
    def parseToInt(value: str, default: int | None = None, positive=True)->int:
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

    def normalize_assets_path(self,path:str,action:Literal['add','remove']='add')-> str:
        if action == 'add':
            return f"{self.ASSETS_DIR}{path}"
        elif action == 'remove':
            return path.removeprefix(self.ASSETS_DIR)
        return path

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

        # MODE CONFIG #
        self.MODE = MODE.toMode(self.getenv('MODE','dev').lower())
        self.PROD_URL = self.getenv('PROD_URL',None)
        self.DEV_URL:str = self.getenv('DEV_URL','http://localhost:8088')

        # CONTAINER CONFIG #
        self.INSTANCE_ID = ConfigService.parseToInt(self.getenv('INSTANCE_ID', '0'),0)
        
        # NAMING CONFIG #
        self.HOSTNAME:str = self.getenv('HOSTNAME',socket.getfqdn())
        self.USERNAME:str = self.getenv('USERNAME','notifyr')

        # DIRECTORY CONFIG #
        self.BASE_DIR:str = self.getenv("BASE_DIR", './')
        self.ASSETS_DIR:str = self.getenv("ASSETS_DIR", f'assets{DIRECTORY_SEPARATOR}')

        # SECURITY CONFIG #
        self.SECURITY_FLAG: bool = ConfigService.parseToBool(self.getenv('SECURITY_FLAG'), False)
        self.ADMIN_KEY:str = self.getenv("ADMIN_KEY")
        self.API_KEY:str = self.getenv("API_KEY")
        
        # SERVER CONFIG #
        self.HTTP_MODE:Literal['HTTP','HTTPS'] = self.getenv("HTTP_MODE",'HTTP')
        self.HTTPS_CERTIFICATE:str = self.getenv("HTTPS_CERTIFICATE", 'cert.pem')
        self.HTTPS_KEY:str = self.getenv("HTTPS_KEY", 'key.pem')

        # EMAIL OAUTH CONFIG #
        self.OAUTH_METHOD_RETRIEVER:str = self.getenv('OAUTH_METHOD_RETRIEVER', 'oauth_custom')  # OAuthFlow | OAuthLib
        self.OAUTH_JSON_KEY_FILE:str = self.getenv('OAUTH_JSON_KEY_FILE')  # JSON key file
        self.OAUTH_TOKEN_DATA_FILE:str = self.getenv('OAUTH_DATA_FILE', 'mail_provider.tokens.json')
        self.OAUTH_CLIENT_ID:str = self.getenv('OAUTH_CLIENT_ID')
        self.OAUTH_CLIENT_SECRET:str = self.getenv('OAUTH_CLIENT_SECRET')
        self.OAUTH_OUTLOOK_TENANT_ID:str = self.getenv('OAUTH_TENANT_ID')

        # ASSETS CONFIG #
        self.ASSET_MODE = AssetMode(self.getenv("ASSET_MODE",'local' if self.MODE == MODE.DEV_MODE else 's3').lower())
        
        # S3 STORAGE CONFIG #
        self.S3_CRED_TYPE:Literal['MINIO','AWS'] = self.getenv('S3_CRED_TYPE','MINIO').upper()

        self.S3_ENDPOINT:str= self.getenv('S3_ENDPOINT','127.0.0.1:9000' if self.MODE == MODE.DEV_MODE else 'minio:9000')

        self.S3_REGION:str = self.getenv("S3_REGION",None)

        self.S3_TO_DISK:bool = ConfigService.parseToBool(self.getenv('S3_TO_DISK','false'), False)

        # MINIO CONFIG #

        self.MINIO_STS_ENABLE:bool = ConfigService.parseToBool(self.getenv('MINIO_STS_ENABLE','false'), False)

        self.MINIO_SSL:bool = ConfigService.parseToBool(self.getenv('MINIO_SSL','false'), False)

        # HASHI CORP VAULT CONFIG #

        self.VAULT_ADDR:str = self.getenv('VAULT_ADDR','http://127.0.0.1:8200' if self.MODE == MODE.DEV_MODE else 'http://vault:8200')

        # MONGODB CONFIG #

        self.MONGO_HOST:str = self.getenv('MONGO_HOST','localhost' if self.MODE == MODE.DEV_MODE else 'mongodb')

        # REDIS CONFIG #

        self.REDIS_URL:str = "redis://"+self.getenv("REDIS_HOST","localhost" if self.MODE == MODE.DEV_MODE else "redis")

        # REDIS CONFIG #
        self.MEMCACHED_URL:str = self.getenv("MEMCHACHED_URL","localhost" if self.MODE == MODE.DEV_MODE else "memcached")

        # SLOW API CONFIG #

        self.SLOW_API_REDIS_URL:str = self.REDIS_URL + self.getenv("SLOW_API_STORAGE_URL", f'/{RedisConstant.LIMITER_DB}')

        # POSTGRES DB CONFIG #

        self.POSTGRES_HOST:str = self.getenv('POSTGRES_HOST','localhost' if self.MODE == MODE.DEV_MODE else 'postgres')

        # CELERY CONFIG #

        self.CELERY_MESSAGE_BROKER_URL = self.getenv("CELERY_MESSAGE_BROKER_URL",self.REDIS_URL +  f'/{RedisConstant.CELERY_DB}')
        self.CELERY_BACKEND_URL =  self.getenv("CELERY_BACKEND_URL", self.REDIS_URL +f'/{RedisConstant.CELERY_DB}')

        self.CELERY_RESULT_EXPIRES = ConfigService.parseToInt(self.getenv("CELERY_RESULT_EXPIRES"), 60*60*24)
        self.CELERY_WORKERS_COUNT = ConfigService.parseToInt(self.getenv("CELERY_WORKERS_COUNT","1"), 1)

    def verify(self):
        if self.S3_CRED_TYPE not in ['MINIO','AWS']:
            raise BuildAbortError(f"S3_CRED_TYPE {self.S3_CRED_TYPE} is not valid please use MINIO or AWS")
        
        if self.HTTP_MODE not in ['HTTP','HTTPS']:
            raise BuildAbortError(f"HTTP_MODE {self.HTTP_MODE} is not valid please use HTTP or HTTPS")
        
        if not self.SECURITY_FLAG:
            raise BuildWarningError(f"SECURITY_FLAG {self.SECURITY_FLAG} is set to False, this is not recommended for production environments")

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


@_service.Service()
class ProcessWorkerService(_service.BaseService):
    ...