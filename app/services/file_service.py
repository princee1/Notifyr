from app.interface.timers import IntervalInterface
from .config_service import ConfigService
from app.definition._service import Service,ServiceClass,AbstractServiceClass
from app.utils.fileIO import FDFlag, readFileContent, getFd, JSONFile, writeContent,listFilesExtension,listFilesExtensionCertainPath, getFileDir, getFilenameOnly
from ftplib import FTP, FTP_TLS
import git_clone as git

@ServiceClass
class FileService(Service,):
    # TODO add security layer on some file: encription,decryption
    # TODO add file watcher
    def __init__(self,configService:ConfigService) -> None:
        super().__init__()
        self.configService = configService
        
    def loadJSON(self):
        pass

    def readFileDetail(self, path, flag:FDFlag, enc="utf-8"):

        filename  = getFilenameOnly(path)
        content = readFileContent(path, flag, enc)
        dirName = getFileDir(path)
        return filename,content,dirName
    
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

    def build(self):
        ...
        
    pass


@AbstractServiceClass
class BaseFileRetrieverService(Service,IntervalInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
    
@ServiceClass
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

    def destroy(self):
        try:
            self.ftpClient.quit()
        except:
            self.ftpClient.close()
    pass

@ServiceClass
class GitCloneRepoService(BaseFileRetrieverService):
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)
    
    def destroy(self):
        return super().destroy()
    pass

@ServiceClass
class AmazonS3BucketService(BaseFileRetrieverService):
    
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)

