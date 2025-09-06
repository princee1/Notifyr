from app.interface.timers import IntervalInterface
from .config_service import ConfigService
from app.definition._service import BaseService,Service,AbstractServiceClass
from app.utils.fileIO import FDFlag, get_file_info, readFileContent, getFd, JSONFile, writeContent,listFilesExtension,listFilesExtensionCertainPath, getFileDir, getFilenameOnly
from ftplib import FTP, FTP_TLS
import git_clone as git

@Service
class FileService(BaseService,):
    # TODO add security layer on some file: encription,decryption
    # TODO add file watcher
    def __init__(self,configService:ConfigService) -> None:
        super().__init__()
        self.configService = configService
        
    def readFileDetail(self, path, flag:FDFlag, enc="utf-8"):

        filename  = getFilenameOnly(path)
        content = readFileContent(path, flag, enc)
        dirName = getFileDir(path)

        return filename,content,dirName

    def get_file_info(self,path):
        return get_file_info(path)
    
    def readFile(self, path,flag:FDFlag,enc= "utf-8"):
        return readFileContent(path, flag, enc)
    
    def writeFile(self,):
        pass

    def listExtensionPath(self, path, extension):
        return listFilesExtensionCertainPath(path,extension)

    def listFileExtensions(self,ext:str,root=None, recursive=False):
        return listFilesExtension(ext,root,recursive)
    
    def _watch(self,path):
        pass

    def addWatcher(self,path,):
        pass

    def build(self,build_state=-1):
        ...
        
    pass


@AbstractServiceClass
class BaseFileRetrieverService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
    
@Service
class FTPService(BaseFileRetrieverService):
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__(configService,fileService)
        self.ftpClient: FTP
        pass

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

@Service
class GitCloneRepoService(BaseFileRetrieverService):
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)
    
    def destroy(self,destroy_state=-1):
        return super().destroy()
    pass

