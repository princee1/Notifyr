
from typing import overload,Type,TypeVar
from warnings import warn




INTERFACES_SET = set()
name = 'Interface'


class MethodConflitException(Exception):
    pass


class Interface:

    def __init_subclass__(cls: type) -> None:
        if cls in INTERFACES_SET:
            if name not in cls.__name__:
                warn(
                    "You should add 'Interface' at the end of your class name for a better QA", stacklevel=2)
            return
        #TODO  compare attributes and methods


I = TypeVar('I',Interface,bound=Type)

def IsInterface(cls: I) -> I:
    INTERFACES_SET.add(cls)
    return cls

