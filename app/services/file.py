from .config import ConfigService
from ._service import Service
from injector import inject
from utils.fileIO import FDFlag, readFileContent, getFd, JSONFile, writeContent
from ftplib import FTP, FTP_TLS


class FileService(Service):

    def __init__(self) -> None:
        super().__init__()

    def build(self):
        return super().build()

    def destroy(self):
        return super().destroy()

    def loadJSON(self):
        pass

    def readFile(self):
        pass

    def writeFile(self,):
        pass

    def listFileExtensions(self):
        pass

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
