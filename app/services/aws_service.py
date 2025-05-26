from app.definition._service import BaseService, Service
from .config_service import ConfigService
from .file_service import BaseFileRetrieverService, FileService


@Service
class AmazonS3Service(BaseFileRetrieverService):
    
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)

@Service
class AmazonSESService(BaseService):
    ...

@Service
class AmazonSNSService(BaseService):
    ...