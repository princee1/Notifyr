
from typing import overload

INTERFACES_SET = set()


class MethodConflitException(Exception):
    pass


class Interface:

    def __init_subclass__(cls:type) -> None:
        if cls in INTERFACES_SET:
            return
        # compare attributes and methods


def IsInterface(cls:type):
    INTERFACES_SET.add(cls)
    return cls


def Implements(cls:type):
    return type(cls.__name__,)