from app.definition._error import BaseError

class LockNotFoundError(BaseError):
    ...

class KeepAliveTimeoutError(BaseError):
    ...

class ReactiveSubjectNotFoundError(BaseError):
    ... 


class ReactiveSubjectAlreadyExist(BaseError):
    ...