from app.definition._error import BaseError


class DataSourceNotSupportedError(BaseError):
    def __init__(self,entered:str,allowed:list[str]):
        super().__init__()
        self.entered =entered
        self.allowed = allowed