from app.definition._error import BaseError
from typing import Any, Literal,TypedDict


class StreamData(TypedDict):
    state:str
    data:Any |dict


class SequentialStateError(BaseError):
    ...

class ContinuousStateError(BaseError):
    ...

class DataParsingError(BaseError):
    ...

class ValidationDataError(BaseError):
    ...
    
StreamType = Literal['continuous','sequential']

class StreamDataParser:

    def __init__(self,state:list[str|int]):
        super().__init__()
        self.state = state
        self._completed =False


    @property
    def completed(self):
        return self._completed

class StreamContinuousDataParser(StreamDataParser):
    
    def up_state(self,state):
        if state not in self.state:
            raise ContinuousStateError
        self.state.remove(state)
    
    def validate_state(self):
        ...

    @property
    def completed(self):
        if self._completed:
            return True
        
        return len(self.state) == 0
    
class StreamSequentialDataParser(StreamContinuousDataParser):
    
    def up_state(self,state):
        if state not in self.state:
            return 
        if self.state[-1] != state:
            raise SequentialStateError(state)
        self.state.pop()