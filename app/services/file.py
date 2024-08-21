from .config import ConfigService
from ._service import Service
from injector import inject
from utils.fileIO import FDFlag, readFileContent, getFd, JSONFile, writeContent,listFilesExtension,listFilesExtensionCertainPath, getFileDir, getFilenameOnly
from ftplib import FTP, FTP_TLS


class FileService(Service):

    def __init__(self) -> None:
        super().__init__()
        
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
    

    pass

class FTPService(Service):
    @inject
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
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
