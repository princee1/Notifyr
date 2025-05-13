from inspect import getmro
from abc import ABC
from random import choice, seed
from string import hexdigits, digits, ascii_letters,punctuation
import time
from inspect import currentframe, getargvalues
from typing import Any, Callable, Literal, Tuple, Type
import urllib.parse
from fastapi import Response
from namespace import Namespace
from str2bool import str2bool
import ast
from enum import Enum
import base64
import urllib
import uuid
import hashlib
import socket

alphanumeric = digits + ascii_letters


################################   ** REST API HELPER Helper **      #################################


def APIFilterInject(func:Callable | Type):

    if type(func) == type:
        annotations = func.__init__.__annotations__.copy()
    else:
        annotations = func.__annotations__.copy()
        annotations.pop('return',None)

    def wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if isinstance(value, (str, int, float, bool, list, dict)) and annotations[key] == Literal  else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return func(*args, **filtered_kwargs)
    return wrapper

def AsyncAPIFilterInject(func:Callable | Type):

    if type(func) == type:
        annotations = func.__init__.__annotations__.copy()
    else:
        annotations = func.__annotations__.copy()
        annotations.pop('return',None)

    async def wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if isinstance(value, (str, int, float, bool, list, dict)) and annotations[key] == Literal  else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return await func(*args, **filtered_kwargs)
    return wrapper

def GetDependency(kwargs:dict[str,Any],key:str|None = None,cls:type|None = None):
    reversed_kwargs = reverseDict(kwargs)
    if key == None and cls == None:
        raise KeyError
    # if cls:
    #     for 
    return 

def copy_response(result:Response,response:Response):
    if not response:
        return result
    result.raw_headers.extend(response.raw_headers)
    result.status_code = response.status_code if response.status_code else result.status_code
    return result

def stable_mac():
    """Generate a stable pseudo-MAC address based on the machine's hostname."""
    hostname = socket.gethostname()
    hash_bytes = hashlib.sha1(hostname.encode()).digest()
    mac = int.from_bytes(hash_bytes[:6], 'big') | 0x010000000000  # Set multicast bit
    return mac & 0xFFFFFFFFFFFF  # Ensure 48-bit value

def uuid_v1_mc():
    """Generate a UUIDv1 with a stable, modified MAC address."""
    return uuid.uuid1(node=stable_mac())


################################   ** Code Helper **      #################################

class SkipCode(Exception):
    pass

################################   ** Key Helper **      #################################


DICT_SEP = "->"

def KeyBuilder(prefix:str|list[str],sep:str|list[str]='-'):

    if prefix == None:
        raise ValueError('prefix cant be None')

    if sep == None:
        raise ValueError('sep cant be None')

    if isinstance(prefix,list) and isinstance(sep,list):
        p_len = len(prefix)
        s_len = len(sep)

        if p_len == 0:
            raise ValueError('prefix cant be an empty list')
        if s_len == 0:
            raise ValueError('sep cant be an empty list')

        if p_len < s_len:
            s_len = [s_len[0]]*p_len

        if p_len != s_len:
            sep = sep[:p_len]

    if isinstance(prefix,list) and isinstance(sep,str):
        sep = [sep]*len(prefix)

    if isinstance(prefix,str) and isinstance(sep,str):
        prefix = [prefix]
        sep= [sep]

    def builder(key:str|list[str])->str:
        if not isinstance(key,str):
            key = [key]

        if len(key) != len(prefix):
            raise ValueError()

        temp = ""
        for p,k,s in zip(prefix,key,sep):
            temp+=f"{p}{s}{k}{s}"
        
        return temp[:-1]

    def separator(key:str)->str:
        if not isinstance(key,str):
            key = [key]

        if len(key) != len(prefix):
            raise ValueError()
        #TODO
        raise NotImplementedError
    
    return builder,separator

def key_builder(key): return key+DICT_SEP


################################   ** Parsing Helper **      #################################


def parseToBool(value: str):
    return str2bool(value, True)


def strict_parseToBool(value: str):
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    return None


def parseToDataStruct(value: str):
    # List or tuple parsing
    try:
        parsed_value = ast.literal_eval(value)
        if isinstance(parsed_value, (list, tuple, dict)):
            return parsed_value
    except (ValueError, SyntaxError):
        return None


# TODO need to add the build error level
def parseToValue(value: str, _type: type[int | bytes | float | bytearray], default: int | bytes | float | bytearray | None = None, ):
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

        if _type not in [int, bytes, float, bytearray]:
            raise AttributeError
        return _type(value)
    except ValueError as e:
        pass
    except TypeError as e:
        pass
    except OverflowError as e:
        pass
    except AttributeError as e:
        pass
    return default


def strict_parseToValue(value: str):
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        return None


def parse_value(value,return_none=False) -> Any | str:
    """
    Parse a string value into the appropriate Python type.
    """
    parsed_value = strict_parseToBool(value)
    if parsed_value is not None:
        return parsed_value

    parsed_value = strict_parseToValue(value)
    if parsed_value is not None:
        return parsed_value

    parsed_value = parseToDataStruct(value)
    if parsed_value is not None:
        return parsed_value

    if return_none:
        return None
    # Default: return the string itself
    return value

################################   ** Dict Helper **      #################################

def reverseDict(value: dict):
    temp = {}
    val = value.values()
    key = reversed(value.keys())
    for v, k in zip(val, key):
        temp[k] = v
    return temp


def swapDict(values: dict):
    """
    The `swapDict` function takes a dictionary as input and returns a new dictionary where the keys and
    values are swapped.

    :param values: A dictionary that you want to swap the keys and values for
    :type values: dict
    :return: The `swapDict` function takes a dictionary `values` as input and returns a new dictionary
    where the keys and values are swapped.
    """
    return {v: k for k, v in values.items()}


def default_flattenReducer(key1:str,key2:str): return  key1+key2

def flatten_dict(current_dict: dict[str, Any], from_keys: str = None, flattenedDict: dict[str,Any] ={}, reducer:Callable[[str,str],str] = default_flattenReducer):
    """
    See https://pypi.org/project/flatten-dict/ for a better implementation
    """
    for key, item in current_dict.items():
        if type(key) is not str:
            continue

        if DICT_SEP in key:
            raise KeyError

        from_keys = "" if from_keys is None else from_keys
        key_val  = reducer(from_keys,key)  

        if type(item) is not dict:
            flattenedDict[key_val] = item

        if type(item) is dict:
            flatten_dict(item, key_builder(key_val), flattenedDict)
    
    return flattenedDict


################################   ** Class Helper **      #################################

def getParentClass(cls: type):
    """
    The function `getParentClass` takes a class as input and returns its immediate parent class.

    :param cls: The `cls` parameter in the `getParentClass` function is expected to be a type object,
    representing a class in Python
    :type cls: type
    """
    return list(getmro(cls)).pop(0)


def create_enum(name: str, values: list):
    return Enum(name, {value.upper(): value for value in values})


def issubclass_of(bCls, kCls):
    return bCls in getmro(kCls)

def isextends_of(obj,bCls):
    return issubclass_of(bCls,type(obj))
    
# WARNING deprecated
def is_abstract(cls: type, bClass: type):
    try:
        x = list(getmro(cls))
        x.remove(cls)
        i = x.index(bClass)
        x.remove(bClass)
        return x.pop(i) == ABC
    except TypeError as e:
        pass 
    except ValueError as e:
        pass
    except:
        pass


def direct_subclass(cls:type):
    return cls.__subclasses__()

primitive_classes = [
    int,         # Integer numbers
    float,       # Floating-point numbers
    complex,     # Complex numbers
    bool,        # Boolean values
    str,         # Strings
    bytes,       # Immutable sequence of bytes
    bytearray,   # Mutable sequence of bytes
    type(None),  # NoneType (the type of `None`)
    type(...),   # Ellipsis (the type of `...`)
    dict,
    list, 
    set,
    frozenset
]


def isprimitive_type(obj:Any):
    return type(obj) in primitive_classes

################################   ** Generate Helper **      #################################

def generateId(len):
    seed(time.time())
    return "".join(choice(alphanumeric) for _ in range(len))


def generateRndNumber(len):
    seed(time.time())
    return "".join(choice(digits) for _ in range(len))


def generateRndNumber(len):
    seed(time.time())
    return "".join(choice(hexdigits) for _ in range(len))


################################## ** Base64 Helper ** #############################################
def b64_encode(value: str)->str:
    return base64.b64encode(value.encode()).decode()

def b64_decode(value: str)->str:
    return base64.b64decode(value.encode()).decode()

###################################### ** URL Helper **  ###########################################

def quote_safe_url(url:str)->str:
    return  urllib.parse.quote(url, safe='~-._')

def unquote_safe_url(url:str)->str:
    return urllib.parse.unquote(url)

def format_url_params(params: dict[str,str])->str:
  """Formats parameters into a URL query string.

  Args:
    params: A key-value map.

  Returns:
    A URL query string version of the given parameters.
  """
  param_fragments = []
  for param in sorted(params.items(), key=lambda x: x[0]):
    param_fragments.append('%s=%s' % (param[0], quote_safe_url(param[1])))
  return '&'.join(param_fragments)



letter_to_number = {
    'A': '2', 'B': '2', 'C': '2',
    'D': '3', 'E': '3', 'F': '3',
    'G': '4', 'H': '4', 'I': '4',
    'J': '5', 'K': '5', 'L': '5',
    'M': '6', 'N': '6', 'O': '6',
    'P': '7', 'Q': '7', 'R': '7', 'S': '7',
    'T': '8', 'U': '8', 'V': '8',
    'W': '9', 'X': '9', 'Y': '9', 'Z': '9'
}


def phone_parser(phone_number:str):
    phone_number = phone_number.upper()
    converted_number = ''.join(letter_to_number.get(
        char, char) for char in phone_number)

    cleaned_number = ''.join(filter(str.isdigit, converted_number))

    if not cleaned_number.startswith('1'):
        cleaned_number = '1' + cleaned_number # ERROR Assuming US OR CA country code

    formatted_number = f"+{cleaned_number}"
    return formatted_number
    
def filter_paths(paths):
        paths = sorted(paths, key=lambda x: x.count("\\"))  # Trier par profondeur
        results = []

        for path in paths:
            if not any(path.startswith(d + "\\") for d in results):
                results.append(path)


        return ['assets/'+ p for p in results ]