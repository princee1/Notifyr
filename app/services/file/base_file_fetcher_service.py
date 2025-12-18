from app.definition._service import AbstractServiceClass, BaseService
from app.interface.timers import IntervalInterface
from app.services.config_service import ConfigService
from app.services.file.file_service import FileService


@AbstractServiceClass()
class BaseFileRetrieverService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService,start_now:bool=False,interval:float=None):
        BaseService.__init__(self)
        IntervalInterface.__init__(self,start_now,interval)
        self.configService = configService
        self.fileService = fileService
    