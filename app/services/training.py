from .config import ConfigService
from .file import FileService
from definition import _service
from injector import inject

class TrainingService(_service.Service):
    @inject
    def __init__(self,configService: ConfigService,fileService:FileService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService
