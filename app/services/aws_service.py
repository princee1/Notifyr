from app.definition._service import ServiceClass
from .config_service import ConfigService
from .file_service import BaseFileRetrieverService, FileService


@ServiceClass
class AmazonS3Service(BaseFileRetrieverService):
    
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)

@ServiceClass
class AmazonSESSNSService():
    ...
