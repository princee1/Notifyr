
from typing import Any, Optional

from aiohttp_retry import Any
from app.definition._error import BaseError


class RedisStreamDoesNotExistsError(BaseError):
    ...

class RedisDatabaseDoesNotExistsError(BaseError):
    ...

class DocumentPrimaryKeyConflictError(BaseError):
    def __init__(self, *args, pk_value=None, model=None,pk_field=None):
        super().__init__(*args)
        self.pk_value = pk_value
        self.model = model
        self.pk_field = pk_field

class DocumentExistsUniqueConstraintError(BaseError):
    def __init__(self, *args,exists=True,model=None,params = {}):
        super().__init__(*args)
        self.exists = exists
        self.model = model
        self.params = params
        

class DocumentDoesNotExistsError(BaseError):
    
    def __init__(self,id, *args):
        super().__init__(*args)
        self.id = id

class DocumentAddConditionError(BaseError):
    def __init__(self,message:str = 'Document does not satisfy the condition to be added',detail:Optional[Any] = None):
        self.message = message
        self.detail = detail
        super().__init__()

class DocumentConditionWrongMethodError(BaseError):
    ...

class DocumentConditionFilterDoesNotExistOnModelError(BaseError):
    ...

    
class DocumentAlreadyDeletedError(BaseError):
    ...

class MongoCollectionDoesNotExists(BaseError):
    ...


class MemCachedTypeValueError(BaseError):
    ...

class MemCacheNoValidKeysDefinedError(BaseError):
    ...

class MemCachedCacheMissError(BaseError):
    ...
