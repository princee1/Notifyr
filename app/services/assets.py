from .config import ConfigService
from utils.fileIO import FDFlag
from classes.template import Asset, HTMLTemplate, PDFTemplate, SMSTemplate, PhoneTemplate, Template
from .security import SecurityService
from .file import FileService, FTPService
from . import _service
from injector import inject
from enum import Enum
import os
from threading import Thread
from typing import Any

ROOT_PATH = "assets/"
def path(x): return ROOT_PATH+x


class Extension(Enum):
    HTML = "html"
    CSS = "css"
    SCSS = "scss"
    JPEG = "jpg"
    PDF = "pdf"
    TXT = "txt"

def extension(extension: Extension): return f".{extension.value}"

class Reader():
    def __init__(self, fileService: FileService, asset:type[Asset]) -> None:
        self.fileService = fileService
        self.asset = asset
        self.values : dict[str,asset] = {}
        
    def read(self, ext: Extension, flag: FDFlag,rootFlag=False,encoding="utf-8"):
        extension_ = extension(ext)
        root = path(ext.value) if rootFlag else None
        setTempFile:set[str]= {}  
        for file in self.fileService.listFileExtensions(extension_, root, recursive=True):
            relpath = root + os.path.sep+file
            filename, content, dir = self.fileService.readFileDetail(relpath, flag,encoding)
            keyName = filename if not setTempFile  else file
            setTempFile.add(keyName)
            self.values[relpath] = self.asset(keyName, content, dir)

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.read(*args)
        return self.values


class ThreadedReader(Reader, Thread): pass # TODO threaded reader

@_service.PossibleDep([FTPService])
class AssetService(_service.Service):
    @inject
    def __init__(self, fileService: FileService, securityService: SecurityService, configService: ConfigService) -> None:
        self.fileService = fileService
        self.securityService = securityService
        self.configService = configService

        self.images: dict[str, Asset] = {}
        self.css: dict[str, Asset] = {}

        self.htmls: dict[str, HTMLTemplate] = {}
        self.pdf: dict[str, PDFTemplate] = {}
        self.sms: dict[str, SMSTemplate] = {}
        self.phone: dict[str, PhoneTemplate] = {}
        pass

    def build(self):
        self.readImages()
        self.readHtml()
        self.readPdf()
        self.readSMS()

    def destroy(self): pass

    def readHtml(self): pass
    
    def readPdf(self): pass

    def readImages(self): pass

    def readSMS(self): pass

    def readCSS(self): pass

    def encryptPdf(self): pass

    def decryptPdf(self): pass
