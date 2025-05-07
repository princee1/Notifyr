import builtins
from dataclasses import dataclass
from typing import Any, Iterator, TypedDict
from typing_extensions import Literal

SubjectType = Literal['contact','plain','message','session']

class MessageError(TypedDict):
    type_:str
    message:Iterator


class MessageBroker(TypedDict):
    subject_id:str
    state:Literal['next','completed','error']
    sid_type:SubjectType
    value:Any
    error:MessageError


def json_to_exception(error:MessageError):
    if error == None:
        return Exception()
    
    message = error['message']
    if not isinstance(message,(list,tuple)):
        message = [message]
    exc_type = error['type_']
    exc_class = getattr(builtins, exc_type, Exception)
    return exc_class(*message)

def exception_to_json(exc: Exception) -> MessageError:
    return {
        'type_': type(exc).__name__,
        'message': list(exc.args)
    }

