from inspect import getmro
from abc import ABC


def issubclass_of(bCls, kCls): return bCls in getmro(kCls)

def isabstract(cls: type, bClass:type):
    try:
        x = list(getmro(cls))
        x.remove(cls)
        i = x.index(bClass)
        x.remove(bClass)
        return x.pop(i) == ABC
    except TypeError as e:
        pass # TODO raise an error, make sure to extends the ABC class last
    except ValueError as e: 
        pass 
    
    except: 
        pass

def reverseDict(value:dict):
    temp = {}
    val = value.values()
    key = reversed(value.keys())
    for v,k in zip(val, key):
        temp[k] = v
    return temp
