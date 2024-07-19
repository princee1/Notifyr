import os
from dotenv import load_dotenv, find_dotenv
from enum import Enum
from module import Module


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
            
class ConfigService(Module):
    
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
        self.EMAIL_HOST = os.getenv("EMAIL_HOST").upper()
        self.EMAIL_PORT = ConfigService.parseToInt(os.getenv("EMAIL_PORT"))
        self.EMAIL = os.getenv("EMAIL")
        self.EMAIL_PASS = os.getenv("EMAIL_PASS")
        self.EMAIL_CONN_METHOD= os.getenv("EMAIL_CONN_METHOD")
        self.EMAIL_LOG_LEVEL= ConfigService.parseToInt(os.getenv("EMAIL_LOG_LEVEL"),0)

    def kill(self):
        return super().kill()
