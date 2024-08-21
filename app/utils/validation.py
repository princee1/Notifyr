import phonenumbers
from validators import url as validate_url, ipv4 as IPv4Address, ValidationError, ipv6 as IPv6Address, email, mac_address
from geopy.geocoders import Nominatim


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
        parsed_phone = phonenumbers.parse(phone, None, keep_raw_input=False)
        return phonenumbers.is_valid_number(parsed_phone)
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

