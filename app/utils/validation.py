from enum import Enum
from typing import Any,Literal
import phonenumbers
from validators import url as validate_url, ipv4 as IPv4Address, ValidationError, ipv6 as IPv6Address, email, mac_address
from geopy.geocoders import Nominatim
from bs4 import Tag
from cerberus import Validator,SchemaError

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
    return validate_url(url)


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
#######################                      #################################

class CustomValidator(Validator):
    def __init__(self,schema) -> None:
        super().__init__(schema)

    def _validate_custom(self,constraint:Literal["ipv4","ipv6","url","mac","email","phone","location","digit"],field,value):
        constraint = constraint.upper()
        if constraint not in ValidatorType._member_names_():
            raise SchemaError
        validator_type = ValidatorType.__getitem__(constraint)
        validationFunc, error_message = validator_type.value
        flag = validationFunc(value)
        if not flag:
            self._error(field, error_message)
    # ERROR extending :check normal validation 
    # TODO for  operator

