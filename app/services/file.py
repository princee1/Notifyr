from ._module import Module
from injector import inject
from utils.fileIO import FDFlag,readFileContent,getFd, JSONFile, writeContent

class FileService(Module):

    def __init__(self) -> None:
        super().__init__()
    
    def build(self):
        return super().build()
    
    def kill(self):
        return super().kill()
    
    def loadJSON(self):
        pass

    def readFile(self):
        pass

    def writeFile(self,):
        pass

    def listFileExtensions(self):
        pass

    pass