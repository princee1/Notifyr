from .config_service import ConfigService
from definition._service import Service,ServiceClass
from injector import inject
from utils.fileIO import FDFlag, readFileContent, getFd, JSONFile, writeContent,listFilesExtension,listFilesExtensionCertainPath, getFileDir, getFilenameOnly
from ftplib import FTP, FTP_TLS
import git_clone as git

# TODO refresh template

@ServiceClass
class FileService(Service):
    # TODO add security layer on some file: encription,decryption
    # TODO add file watcher
    def __init__(self,configService:ConfigService) -> None:
        super().__init__()
        self.configService = configService
        
    def loadJSON(self):
        pass

    def readFileDetail(self, path, flag, enc="utf-8"):

        filename  = getFilenameOnly(path)
        content = readFileContent(path, flag, enc)
        dirName = getFileDir(path)
        return filename,content,dirName
    
    def readFile(self, path,flag,enc= "utf-8"):
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

    pass

@ServiceClass
class FTPService(Service):
    @inject
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__()

        self.configService = configService
        self.fileService = fileService
        self.ftpClient: FTP
        pass

    def authenticate(self):
        try:
            self.ftpClient = FTP()
            self.ftpClient.set_debuglevel()
            result = self.ftpClient.login()
        except:
            pass

    def build(self):
        self.authenticate()

    def destroy(self):
        try:
            self.ftpClient.quit()
        except:
            self.ftpClient.close()
    pass

@ServiceClass
class GitCloneRepoService(Service):
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__()
        self.configService = configService
        self.fileService = fileService

    def build(self):
        return super().build()
    
    def destroy(self):
        return super().destroy()
    pass