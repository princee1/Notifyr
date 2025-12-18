from app.definition._service import BaseService, Service
from app.services.file.file_service import FileService
from app.services.config_service import ConfigService

@Service()
class QdrantService(BaseService):
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService