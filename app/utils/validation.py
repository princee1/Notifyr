from enum import Enum
from typing import Any,Literal
import phonenumbers
from validators import url as validate_url, ipv4 as IPv4Address, ValidationError, ipv6 as IPv6Address, email, mac_address
from geopy.geocoders import Nominatim
from bs4 import Tag
from cerberus import Validator,SchemaError
from datetime import datetime
from functools import wraps
import re
import ipaddress
from .transformer import transform
from langcodes import Language


def ipv4_validator(ip):
    """
    The `ipv4_validator` function checks if a given input is a valid IPv4 address.
    """
    try:
        return IPv4Address(ip)
    except ValidationError as e:
        return False


def ipv6_validator(ip):
    """
    The function `ipv6_validator` checks if a given input is a valid IPv6 address.
    """
    try:
        return IPv6Address(ip)
    except ValidationError:
        return False


def ipv4_subnet_validator(ip):
    """
    The function `ipv4_subnet_validator` checks if a given input is a valid IPv4 subnet.
    """
    try:
        ipaddress.IPv4Network(ip, strict=False)
        return True
    except ValueError:
        return False
    except ipaddress.NetmaskValueError:
        return False
    except:
        return False


def email_validator(e_mail):
    """
    The function `email_validator` uses a regular expression to validate if an email address is in a
    correct format.
    """
    # Simple regex for validating an email
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    try:
        return email(e_mail)
    except:
        return False


def phone_number_validator(phone):
    try:
        parsed_phone = phonenumbers.parse(phone, None)
        return phonenumbers.is_valid_number(parsed_phone) and phonenumbers.is_possible_number(parsed_phone)
    except phonenumbers.phonenumberutil.NumberParseException:
        return False


def url_validator(url):
    """
    The function `url_validator` takes a URL as input and validates the URL format
    """
    try:
        return validate_url(url)
    except:
        return False


def mac_address_validator(mac):
    """
    The function `mac_address_validator` attempts to validate a MAC address and returns True if
    successful, otherwise False.
    """
    try:
        return mac_address(mac)
    except:
        return False


def location_validator(latitude, longitude):
    raise NotImplementedError()
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return False
    geolocator = Nominatim(user_agent="geoapiExercises")
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    return location is not None


def digit_validator(val:int):
    return val>=0 and val <=9


def date_validator(date: str) -> bool:
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def time_validator(time: str) -> bool:
    try:
        datetime.strptime(time, "%H:%M:%S")
        return True
    except ValueError:
        return False
    

def PasswordValidator(min_length=8, max_length=128, require_digit=True, require_symbol=True, require_uppercase=True):

        def validator(password: str) -> str:
            if len(password) < min_length or len(password) > max_length:
                raise ValueError(f"Password must be between {min_length} and {max_length} characters long.")
            if require_digit and not any(char.isdigit() for char in password):
                raise ValueError("Password must contain at least one digit.")
            if require_symbol and not any(char in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for char in password):
                raise ValueError("Password must contain at least one symbol.")
            if require_uppercase and not any(char.isupper() for char in password):
                raise ValueError("Password must contain at least one uppercase letter.")
            return password
        return validator

    
def language_code_validator(language):
    try:
        return Language.get(language).is_valid()
    except:
        return False

#######################                      #################################
class ValidatorType(Enum):
    IPV4= ipv4_validator,"Must be an ipv4 address format"
    IPV6=ipv6_validator,"Must be an ipv6 address format"
    MAC=mac_address_validator,"Must be an mac address format"
    PHONE=phone_number_validator,"Must be an phone number format"
    EMAIL=email_validator,"Must be an email address format"
    LOCATION=location_validator,"Must be an geolocation location format"
    URL=url_validator,"Must be an url address format"
    DIGIT=digit_validator,"Must be a digit"
    DATE = date_validator,"Must be a date format Y-M-D"
    TIME = time_validator,"Must be a time format H:M:S"
    LANG = language_code_validator,"Must be a valid language code format" 
#######################                      #################################

class CustomValidator(Validator):
    def __init__(self,schema) -> None:
        super().__init__(schema)

    def _validate_custom(self,constraint:Literal["ipv4","ipv6","url","mac","email","phone","location","digit"],field,value):
        constraint = constraint.upper()
        if constraint not in ValidatorType._member_names_:
            raise SchemaError
        validator_type = ValidatorType.__getitem__(constraint)
        validationFunc, error_message = validator_type.value
        flag = validationFunc(value)
        if not flag:
            self._error(field, error_message)
    
    def _validate_transform(self,constraint:str,field,value):
        if not constraint:
            self._error(field,'Must be a valid string')
        
        if constraint not in transform:
            self._error(field,'Transformer does not exists')

    # ERROR extending :check normal validation 
    # TODO for  operator

