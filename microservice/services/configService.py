import os
from dotenv import load_dotenv
from enum import Enum
from __init__ import Service


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
            
class ConfigService(Service):
    ENV = ".env"
    def __init__(self) -> None:
        load_dotenv(ConfigService.ENV)
        self.MODE = MODE.toMode(os.getenv('MODE'))
        self.PORT = os.getenv("PORT")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL")
        self.EMAIL_HOST = os.getenv("EMAIL_HOST").upper()
        try:
            val = int(os.getenv("EMAIL_PORT"))
            self.EMAIL_PORT = val
        except:

            self.EMAIL_PORT = None
            pass
        self.EMAIL = os.getenv("EMAIL")
        self.EMAIL_PASS = os.getenv("EMAIL_PASS")
        self.EMAIL_CONN_METHOD= os.getenv("EMAIL_CONN_METHOD")
        try: 
            self.EMAIL_LOG_LEVEL= int(os.getenv("EMAIL_LOG_LEVEL"))
        except:
            self.EMAIL_LOG_LEVEL = 0
            pass


    def buildService(self):
        pass