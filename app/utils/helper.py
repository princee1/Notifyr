from inspect import getmro
from abc import ABC
from random import choice, seed
from string import hexdigits, digits, ascii_letters 
import time

alphanumeric = digits + ascii_letters

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
