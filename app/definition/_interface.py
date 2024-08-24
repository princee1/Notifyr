from utils.helper import issubclass_of

class Interface:
    pass

def implements(interface:type[Interface]):
    # TODO checks all the 
    def wrapper(cls:type):
        return cls
    return wrapper
