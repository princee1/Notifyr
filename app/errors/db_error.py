
from app.definition._error import BaseError


class RedisStreamDoesNotExistsError(BaseError):
    ...

class RedisDatabaseDoesNotExistsError(BaseError):
    ...

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