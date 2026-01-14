import asyncio
from inspect import getmro
from abc import ABC
import json
from random import choice, seed
import random
from string import hexdigits, digits, ascii_letters,punctuation
import time
from typing import Any, Callable, Literal, Optional, Union,Tuple, Type, TypeVar, get_args, get_origin
import urllib.parse
from cachetools import Cache
from fastapi import Response
from pydantic import BaseModel, ConfigDict, create_model
from pydantic_core import PydanticUndefined
from str2bool import str2bool
import ast
from enum import Enum
import base64
import urllib
from uuid import UUID,uuid1
import hashlib
import socket

from app.utils.globals import DIRECTORY_SEPARATOR

alphanumeric = digits + ascii_letters


################################   ** REST API HELPER Helper **      #################################


def APIFilterInject(func:Callable | Type):

    if type(func) == type:
        annotations = func.__init__.__annotations__.copy()
    else:
        annotations = func.__annotations__.copy()
        annotations.pop('return',None)

    def sync_wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if isinstance(value, (str, int, float, bool, list, dict)) and annotations[key] == Literal  else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return func(*args, **filtered_kwargs)
    
    async def async_wrapper(*args,**kwargs):
        filtered_kwargs = {
            key: (annotations[key](value) if isinstance(value, (str, int, float, bool, list, dict)) and annotations[key] == Literal  else value)
            for key, value in kwargs.items()
            if key in annotations
        }
        return await func(*args, **filtered_kwargs)

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

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
    if response == None:
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

def uuid_v1_mc(len=1):
    """Generate a UUIDv1 with a stable, modified MAC address."""
    if len <=0:
        raise ValueError('len needs to be positive and non null')
    if len==1:
        return uuid1(node=stable_mac())
    return [uuid1(node=stable_mac()) for _ in range(len)]


################################   ** Code Helper **      #################################

class SkipCode(Exception):
    
    def __init__(self,result=None,_return=False, *args):
        super().__init__(*args)
        self.result = result
        self._return = _return

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
        if isinstance(key,str):
            key = [key]

        if len(key) != len(prefix):
            raise ValueError('')

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


################################   ** Helper **      #################################

def get_value_in_list(data,index):
    try:
        return data[index]
    except:
        return None


class PointerIterator:

    class Pointer:
        def __init__(self,ptr:object |dict,data_key:str,type_:type[object | dict]):
            self.ptr = ptr
            self.data_key = data_key
            self._type = type_

        def get_val(self):
            if self._type == object:
                return getattr(self.ptr,self.data_key,None)
            if isinstance(self.ptr,dict):
                if self.data_key not in self.ptr:
                    return False,None
                return True,self.ptr[self.data_key]
            return None
    
        def set_val(self,new_val):
            if self._type == object:
                setattr(self.ptr,self.data_key,new_val)
            else:
                if isinstance(self.ptr,dict):
                    self.ptr[self.data_key] = new_val

        def del_val(self):
            exists = self.get_val()
            if self._type == object:
                if exists == None:
                    return None
                delattr(self.ptr,self.data_key)
                return exists
            else:
                exists,val= exists
                if not exists:
                    return None
                self.ptr.pop(self.data_key,None)   
                return val  

    def __init__(self,var:str,split:str='.',_type:Type[object|dict]=object):
        self._type=_type
        self.var = var
        if var== None:
            raise ValueError(f'var cant be None')
        self.ptr_iterator = var.split(split)
    
    def ptr(self,value:object|dict):
        ptr = value
        for sk in self.ptr_iterator[:-1]:
            if ptr == None:
                break
            if self._type == object:
                next_ptr =getattr(ptr,sk,None) 
            else:
                next_ptr = ptr.get(sk,None)
                if not isinstance(next_ptr,dict):
                    break
            ptr = next_ptr
        
        return self.Pointer(ptr,self.data_key,self._type)
    
    @property
    def data_key(self):
        return self.ptr_iterator[-1]
    
       

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
    
def enum_encoder(obj):
    if isinstance(obj, Enum):
        return obj.value  # or obj.value if you prefer
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

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

def flatten_dict(current_dict: dict[str, Any], from_keys: str = None, flattenedDict: dict[str,Any] =None, reducer:Callable[[str,str],str] = default_flattenReducer,serialized=False,dict_sep=DICT_SEP,_key_builder=key_builder,max_level=-1,current_level=0):
    """
    See https://pypi.org/project/flatten-dict/ for a better implementation
    """
    flattenedDict = {} if flattenedDict == None else flattenedDict

    for key, item in current_dict.items():
        if type(key) is not str:
            continue

        if dict_sep in key:
            raise KeyError

        from_keys = "" if from_keys is None else from_keys
        key_val  = reducer(from_keys,key)  

        if type(item) is not dict:
            flattenedDict[key_val] = item if not serialized else json.dumps(item,default=enum_encoder)
        else:
            if max_level>0 and current_level>=max_level:
                flattenedDict[key_val]=item
            else:
                flatten_dict(item, _key_builder(key_val), flattenedDict,reducer,serialized,dict_sep,_key_builder,max_level=max_level,current_level=current_level+1)
    
    return flattenedDict

def unflattened_dict(flattened_dict: dict[str, Any], separator: str = DICT_SEP) -> dict[str, Any]:
    """
    Converts a flattened dictionary back into a nested dictionary, attempting to parse JSON values back to their original types.
    """
    unflattened = {}
    for key, value in flattened_dict.items():
        keys = key.split(separator)
        current = unflattened
        for part in keys[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        try:
            current[keys[-1]] = json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            current[keys[-1]] = value
    return unflattened



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

def generateId(len, add_punctuation=False):
    seed(time.time())
    if add_punctuation:
        return "".join(choice(alphanumeric + punctuation) for _ in range(len))
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

###################################### ** Phone Helper **  ###########################################

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


def phone_parser(phone_number:str,country_code=None):
    phone_number = phone_number.upper()
    converted_number = ''.join(letter_to_number.get(
        char, char) for char in phone_number)

    plus_exists = converted_number.startswith('+')
    cleaned_number = ''.join(filter(str.isdigit, converted_number))

    if not plus_exists:
        if country_code == None:
            raise ValueError('Country cannot be null')
        cleaned_number = f'+{country_code}{phone_number}'
    else:
        cleaned_number = f'+{phone_number}'
    return cleaned_number

def filter_paths(paths: list[str],sep=DIRECTORY_SEPARATOR) -> list[str]:
        paths = sorted(paths, key=lambda x: x.count(sep))  # Trier par profondeur
        results = []
        if sep in paths:
            return [sep]
        for path in paths:
            if not any(path.startswith(d + sep) for d in results):
                results.append(path)
        return results

###################################### ** Time Helper **  ###########################################

from croniter import croniter
from datetime import datetime, timedelta


def time_until_next_tick(cron_expr: str) -> float:
    """
    Calculate how many seconds until the next cron tick
    from the current time.
    """
    base = datetime.now()
    itr = croniter(cron_expr, base)
    next_time = itr.get_next(datetime)
    return (next_time - base).total_seconds()

def cron_interval(cron_expr: str, start_time: float) -> float:
    base = datetime.fromtimestamp(start_time)
    itr = croniter(cron_expr, base)
    t1 = itr.get_next(datetime)
    t2 = itr.get_next(datetime)
    return (t2 - t1).total_seconds()

def _make_delay_fn(
    *,
    fixed: float | None = None,
    fn: Callable[[], float] | None = None,
    uniform: tuple[float, float] | None = None,
    normal: tuple[float, float] | None = None,
    exponential: float | None = None,
) -> Callable[[], float]:
    """
    Returns a zero-arg function producing a delay (seconds)
    """

    if fixed is not None:
        return lambda: fixed

    if fn is not None:
        return fn

    if uniform is not None:
        a, b = uniform
        return lambda: random.uniform(a, b)

    if normal is not None:
        mu, sigma = normal
        return lambda: max(0.0, random.gauss(mu, sigma))

    if exponential is not None:
        return lambda: random.expovariate(exponential)

    raise ValueError("Throttle requires a delay strategy")

###################################### ** Model Helper **  ###########################################
def is_optional(annotation) -> bool:
    """Check if a type annotation already allows None"""
    if annotation is None:
        return True
    origin = get_origin(annotation)
    if origin is Union:
        return type(None) in get_args(annotation)
    return False

M= TypeVar('M',bound=BaseModel)

def subset_model(
    base: Type[M],
    name: str,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    optional: bool = True,
    __config__:ConfigDict |None = None
)->Type[M]:
    fields = {}
    for field_name, field in base.model_fields.items():
        if include and field_name not in include:
            continue
        if exclude and field_name in exclude:
            continue

        ann = field.annotation
        default = field.default if field.default is not None else ...

        if optional:
            if not is_optional(ann):
                ann = Optional[ann]  # only wrap if not already Optional

            if default is PydanticUndefined or ...:
                default = None 
    
        fields[field_name] = (ann, default)
    
    return create_model(name,__config__=__config__, **fields)

################################   ** Cache Helper **      #################################


class IntegrityCache:
    """
    The `IntegrityCache` class implements a caching mechanism with support for two modes:
    'presence-only' which only checks if the value is inside of the cache and 'value' checks the presence and the integrity of the value.
    """

    def __init__(self,mode:Literal['presence-only','value'],_cache:Callable[[],dict|Cache]=lambda:dict()):
        self._cache_init = _cache
        self.mode = mode
        self.init()

    def init(self):
        self._cache = self._cache_init()
        
    def cache(self,key,value=None)->bool:
        """
        Return if it is a cache hit. If the mode is `value` then it performs also the value validation
        """
        if self.mode == 'presence-only':
            value = None

        if key not in self._cache:
            self._cache[key]=value
            return False
        
        if self.mode == "presence-only":
            return True
        
        if self._cache[key] == value:
            return True

        self._cache[key] = value
        return False

    def clear(self):
        self.init()
    
    def invalid(self,key:str,default:Any=None):
        return self._cache.pop(key,default)