class Interface:
    pass

def implements(interface:type[Interface]):
    def wrapper(cls:type):
        return cls
    return wrapper
