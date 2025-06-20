from app.services.email_service import EmailReaderService
from .config_service import ConfigService
from .file_service import FileService
from app.definition import _service
from injector import inject

@_service.Service
class LLMModelService(_service.BaseService):
    @inject
    def __init__(self, configService: ConfigService, fileService: FileService,emailReaderService:EmailReaderService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService
        self.emailReaderService =emailReaderService

