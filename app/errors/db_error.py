from typing import Any, Optional
from aiohttp_retry import Any
from app.definition._error import BaseError


###############################################################################################################################
#############################################                                                      ############################
###############################################################################################################################

class VaultCredentialAlreadyExistError(BaseError):
    def __init__(self,name):
        super().__init__(name)
        self.name = name

class VaultCredentialNameDoesNotExistError(BaseError):
    def __init__(self,name):
        super().__init__(name)
        self.name = name

###############################################################################################################################
#############################################                                                      ############################
###############################################################################################################################


class RedisStreamDoesNotExistsError(BaseError):
    ...

class RedisDatabaseDoesNotExistsError(BaseError):
    ...

###############################################################################################################################
#############################################                                                      ############################
###############################################################################################################################


class DocumentPrimaryKeyConflictError(BaseError):
    def __init__(self, *args, pk_value=None, model=None,pk_field=None):
        super().__init__(*args)
        self.pk_value = pk_value
        self.model = model
        self.pk_field = pk_field

class CollectionHardLimitReachedError(BaseError):

    def __init__(self, limit:int,collection:str):
        super().__init__(limit,collection,)
        self.limit = limit
        self.collection = collection

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
    def __init__(self,message:str = None,detail:Optional[Any] = None):
        self.message = message or 'Document does not satisfy the condition to be added'
        self.detail = detail
        super().__init__()

class DocumentSingletonLimitReachedError(BaseError):
    def __init__(self, document_id:str,alias:str):
        super().__init__(document_id,alias)
        self.document_id = document_id
        self.alias = alias

class DocumentConditionWrongMethodError(BaseError):
    ...

class DocumentConditionFilterDoesNotExistOnModelError(BaseError):
    ...

    
class DocumentAlreadyDeletedError(BaseError):
    ...

class MongoCollectionDoesNotExists(BaseError):
    def __init__(self, collection:str,model:str=None):
        super().__init__(collection,model)
        self.collection = collection
        self.model = model


class MongoClientDataDoesNotExistError(BaseError):
    def __init__(self,name):
        super().__init__(name)
        self.name = name

class MongoClientAlreadyExistError(BaseError):
    def __init__(self,name,mode):
        super().__init__(name,mode)
        self.name = name
        self.mode =mode

class MongoClientModeDoesNotExistError(BaseError):
    def __init__(self,name,mode):
        super().__init__(name,mode)
        self.name = name
        self.mode = mode

###############################################################################################################################
#############################################                                                      ############################
###############################################################################################################################

class MemCachedTypeValueError(BaseError):
    ...

class MemCacheNoValidKeysDefinedError(BaseError):
    ...

class MemCachedCacheMissError(BaseError):
    ...
