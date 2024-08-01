from .security import SecurityService
from .file import FileService
from . import _module
from injector import inject
from enum import Enum


class Extension(Enum):
    HTML = ".html"
    CSS = ".css"
    SCSS = ".scss"
    JPEG = ".jpg"
    PDF = ".pdf"
    TXT = ".txt"


class AssetService(_module.Module):
    @inject
    def __init__(self, fileService: FileService, securityService: SecurityService) -> None:
        self.fileService = fileService
        self.images = {}
        self.htmls = {}
        self.pdf = {}
        self.sms = {}
        self.css = {}
        pass

    def build(self): pass

    def destroy(self): pass

    def readHtml(self): pass

    def readPdf(self): pass

    def readImages(self): pass

    def readSMS(self): pass

    def loadCss(self): pass

    def encryptPdf(self): pass

    def decryptPdf(self): pass

    pass
