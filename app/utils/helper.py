from inspect import getmro
from abc import ABC
from random import choice, seed
from string import hexdigits, digits, ascii_letters 
import time
from inspect import currentframe, getargvalues
from typing import Any
from namespace import Namespace
from str2bool import str2bool
import ast

class SkipCode(Exception): pass

alphanumeric = digits + ascii_letters

def parseToBool(value: str):
    return str2bool(value,True)

def strict_parseToBool(value: str):
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    return None

def parseToDataStruct(value:str):
    # List or tuple parsing
    try:
        parsed_value = ast.literal_eval(value)
        if isinstance(parsed_value, (list, tuple, dict)):
            return parsed_value
    except (ValueError, SyntaxError):
        return None

def parseToValue(value:str, _type: type[int | bytes | float | bytearray],default:int | bytes | float | bytearray | None = None, ): # TODO need to add the build error level
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

            if  _type not in [int, bytes, float, bytearray]:
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

def strict_parseToValue(value:str):
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        return None

def parse_value(value) -> Any | str:
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
    
    # Default: return the string itself
    return value

def issubclass_of(bCls, kCls): return bCls in getmro(kCls)

def is_abstract(cls: type, bClass: type):  # BUG
    try:
        x = list(getmro(cls))
        x.remove(cls)
        i = x.index(bClass)
        x.remove(bClass)
        return x.pop(i) == ABC
    except TypeError as e:
        pass  # TODO raise an error, make sure to extends the ABC class last
    except ValueError as e:
        pass
    except:
        pass

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

def getParentClass(cls: type): 
    """
    The function `getParentClass` takes a class as input and returns its immediate parent class.
    
    :param cls: The `cls` parameter in the `getParentClass` function is expected to be a type object,
    representing a class in Python
    :type cls: type
    """
    return list(getmro(cls)).pop(0)
   
def generateId(len):
    seed(time.time())
    return "".join(choice(alphanumeric) for _ in range(len))

def generateRndNumber(len):
    seed(time.time())
    return "".join(choice(digits) for _ in range(len))

def generateRndNumber(len):
    seed(time.time())
    return "".join(choice(hexdigits) for _ in range(len))
 