from app.interface.timers import IntervalInterface
from app.definition._service import GUNICORN_BUILD_STATE, BaseService,Service,AbstractServiceClass
from ftplib import FTP, FTP_TLS
import git_clone as git
from app.services.config_service import AssetMode, ConfigService
from app.services.file.base_file_fetcher_service import BaseFileRetrieverService
from app.services.file.file_service import FileService
from app.utils.helper import PointerIterator


@Service()
class FTPService(BaseFileRetrieverService):
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__(configService,fileService)
        self.ftpClient: FTP
        pass

    def build(self, build_state = ...):
        if build_state != GUNICORN_BUILD_STATE:
            return
        
        if self.configService.ASSET_MODE != AssetMode.ftp:
            return
        
    def authenticate(self):
        try:
            self.ftpClient = FTP()
            self.ftpClient.set_debuglevel()
            result = self.ftpClient.login()
        except:
            pass

    def destroy(self,destroy_state=-1):
        try:
            self.ftpClient.quit()
        except:
            self.ftpClient.close()
    pass

@Service()
class GitCloneRepoService(BaseFileRetrieverService):
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)
    
    def build(self, build_state = ...):
        if build_state != GUNICORN_BUILD_STATE:
            return
        
        if self.configService.ASSET_MODE != AssetMode.github:
            return
        

    def destroy(self,destroy_state=-1):
        return super().destroy()
    pass

