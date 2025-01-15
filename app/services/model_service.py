from .config_service import ConfigService
from .file_service import FileService
from definition import _service
from injector import inject

@_service.ServiceClass
class TrainingService(_service.Service):
    @inject
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService
