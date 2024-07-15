import os
from dotenv import load_dotenv
from enum import Enum


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
            
class ConfigService():
    ENV = ".env"
    def __init__(self) -> None:
        load_dotenv(ConfigService.ENV)
        self.MODE = MODE.toMode(os.getenv('MODE'))
        self.PORT = os.getenv("PORT")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL")
        self.EMAIL_HOST = os.getenv("EMAIL_HOST").capitalize()
        self.EMAIL_PORT = os.getenv("EMAIL_PORT")
        self.EMAIL = os.getenv("EMAIL")
        self.EMAIL_PASS = os.getenv("EMAIL_PASS")
