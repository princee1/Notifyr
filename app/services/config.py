import os
from dotenv import load_dotenv, find_dotenv
from enum import Enum

from utils.helper import parseToInt
from . import _service
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

            
class ConfigService(_service.Service):
    
    def __init__(self) -> None:
        super().__init__()
        if not load_dotenv(ENV):
            path = find_dotenv(ENV)
            load_dotenv(path)
    
    def build(self):
        self.MODE = MODE.toMode(os.getenv('MODE'))
        self.PORT_PUBLIC = parseToInt(os.getenv("PORT_PUBLIC"),3000)
        self.PORT_PRIVATE = parseToInt(os.getenv("PORT_PRIVATE"),5000)
        self.LOG_LEVEL = parseToInt(os.getenv("LOG_LEVEL"), 2)

        self.SMTP_EMAIL_HOST = os.getenv("SMTP_EMAIL_HOST").upper()
        self.SMTP_EMAIL_PORT = parseToInt(os.getenv("SMTP_EMAIL_PORT"))
        self.SMTP_EMAIL = os.getenv("SMTP_EMAIL")
        self.SMTP_PASS = os.getenv("SMTP_EMAIL_PASS")
        self.SMTP_EMAIL_CONN_METHOD= os.getenv("SMTP_EMAIL_CONN_METHOD")
        self.SMTP_EMAIL_LOG_LEVEL= ConfigService.parseToInt(os.getenv("SMTP_EMAIL_LOG_LEVEL"),0)

        self.IMAP_EMAIL_HOST = os.getenv("IMAP_EMAIL_HOST").upper()
        self.IMAP_EMAIL_PORT = parseToInt(os.getenv("IMAP_EMAIL_PORT"))
        self.IMAP_EMAIL = os.getenv("IMAP_EMAIL")
        self.IMAP_EMAIL_PASS = os.getenv("IMAP_EMAIL_PASS")
        self.IMAP_EMAIL_CONN_METHOD= os.getenv("IMAP_EMAIL_CONN_METHOD")
        
    def destroy(self):
        return super().destroy()
