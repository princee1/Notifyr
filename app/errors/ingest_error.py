from typing_extensions import Literal
from app.definition._error import BaseError
from app.utils.constant import ArqDataTaskConstant

Database = Literal['vector','graph']
ConfigDatabase = Literal['vector_config','graph_config']

class AgenticDatabaseNotAllowedError(BaseError):
    def __init__(self,database:Database):
        super().__init__(database)
        self.database = database
    

class IngestConfigNotPresentError(BaseError):
    def __init__(self,config_name:ConfigDatabase, database:Database):
        super().__init__(database)
        self.config_name = config_name
        self.database = database

class TaskIngestNameNotValidError(BaseError):
    def __init__(self, task:str,database:Database):
        super().__init__(task)
        self.task = task
        self.database = database

class SizeIngestNotFoundError(BaseError):
    def __init__(self, task:ArqDataTaskConstant._DATA_TASK_TYPE,uri:str,database:Database):
        super().__init__(task,uri,database)
        self.task = task
        self.uri = uri
        self.database = database

class IngestTaskNotSupportedError(BaseError):
    def __init__(self, task:str):
        super().__init__()
        self.task = task