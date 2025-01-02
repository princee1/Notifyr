import jwt 
from utils.prettyprint import PrettyPrinter_
from utils.question import ask_question,CheckboxInputHandler,ConfirmInputHandler,SimpleInputHandler
from dotenv import load_dotenv
import os 
from random import randint
import time
import base64

from cryptography.fernet import Fernet

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
API_KEY = os.getenv("API_KEY")
ON_TOP_SECRET_KEY = os.getenv("ON_TOP_SECRET_KEY")
API_ENCRYPT_TOKEN = os.getenv("API_ENCRYPT_TOKEN")


SEPARATOR = "|"

def generate_custom_api_key(ip_address:str):
    data = ip_address + SEPARATOR + str(randint(0,1000000)) + SEPARATOR + str(time.time()) + SEPARATOR + API_KEY
    data  = base64.b64encode(data.encode()).decode()
    cipher_suite = Fernet(API_ENCRYPT_TOKEN)
    return cipher_suite.encrypt(data.encode()).decode()
