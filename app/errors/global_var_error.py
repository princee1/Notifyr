from app.definition._error import BaseError
from app.utils.helper import DICT_SEP


class GlobalKeyBaseError(BaseError):
    def __init__(self,sep:str,key:str, *args):
        super().__init__(*args)
        self.sep = sep
        self._key = key
    
    @property
    def key(self):
        return self._key.replace(DICT_SEP,self.sep)


class GlobalKeyAlreadyExistsError(GlobalKeyBaseError):
    ...


class GlobalKeyDoesNotExistsError(GlobalKeyBaseError):
    ...