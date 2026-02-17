from typing_extensions import Literal
from app.definition._error import BaseError


class AgenticDatabaseNotAllowedError(BaseError):
    def __init__(self,database:Literal['vector','kgraph']):
        super().__init__(database)
        self.database = database
    

class IngestConfigNotPresentError(BaseError):
    def __init__(self,config_name:str, database:Literal['vector','kgraph']):
        super().__init__(database)
        self.config_name = config_name
        self.database = database