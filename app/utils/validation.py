import phonenumbers
from validators import url as validate_url, ipv4 as IPv4Address, ValidationError, ipv6 as IPv6Address, email, mac_address
from geopy.geocoders import Nominatim
from bs4 import Tag
from cerberus import Validator




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


class SchemaBuilder:pass


class HtmlSchemaBuilder (SchemaBuilder):
    VALIDATION_ITEM_SELECTOR = "validation-item"
    CurrentHashRegistry = {}
    HashSchemaRegistry = {}



    def __init__(self, root) -> None:
        self.root: Tag = root
        self.schema: dict[str, dict] = self.find(self.root)
    def find(self, validation_item: Tag):
        schema: dict[str,dict | str] = {}
        for validator in validation_item.find_all(HtmlSchemaBuilder.VALIDATION_ITEM_SELECTOR,recursive=False):
            v: Tag = validator
            has_noSuccessor = len(v.find_all(HtmlSchemaBuilder.VALIDATION_ITEM_SELECTOR)) == 0
            if not has_noSuccessor:
                v.attrs["type"] = "dict"
            if not v.attrs.__contains__("type"):
                v.attrs["type"] = "string"	
            key = v.attrs["id"]
            # TODO validates arguments
            schema[key] = {_id: val for _id,val in v.attrs.items() if _id != "id"}
            if has_noSuccessor:
                # TODO
                # if schema[key].__contains__("schema"):
                #     default_schema_registry = schema[key]["schema"]
                #     if type(default_schema_registry) == str and default_schema_registry in HtmlSchemaBuilder.HashSchemaRegistry.keys():
                #         default_schema_registry = HtmlSchemaBuilder.HashSchemaRegistry[default_schema_registry]
                continue
            successor_schema =  self.find(v)
            schema[key]["schema"] = successor_schema
        return schema
    
    def parse(self):
        pass


class CustomValidator(Validator):
    def __init__(self,schema) -> None:
        super().__init__(schema)

