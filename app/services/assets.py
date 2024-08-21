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
from typing import Any, Callable
from utils.helper import issubclass_of

ROOT_PATH = "assets/"
def path(x): return ROOT_PATH+x


class Extension(Enum):
    """
    The class `Extension` defines an enumeration of file extensions.
    """

    HTML = "html"
    CSS = "css"
    SCSS = "scss"
    JPEG = "jpg"
    PDF = "pdf"
    TXT = "txt"
    SMS = "sms"
    PHONE = "ph"


class AssetType(Enum):
    IMAGES = "images"
    SMS = "sms"
    PHONE = "phone"
    HTML = Extension.HTML.value


def extension(extension: Extension): return f".{extension.value}"


class Reader():
    fileService: FileService

    def __init__(self, asset: type[Asset] = Asset, additionalCode: Callable = None) -> None:
        self.asset = asset
        self.values: dict[str, asset] = {}
        self.func = additionalCode

    def safeReader(self, ext: Extension, flag: FDFlag, rootFlag: bool | str = True, encoding="utf-8"):
        try:
            self.read(ext, flag, rootFlag, encoding)
        except OSError as e:
            pass
        except TypeError as e:
            pass
        except AttributeError as e:
            pass

    def read(self, ext: Extension, flag: FDFlag, rootParam: str = None, encoding="utf-8"):
        """
        This function reads files with a specific extension, processes them, and stores the content in a
        dictionary.

        :param ext: It is used to specify the file extension that you want to read
        :type ext: Extension
        :param flag:It is likely used to control how the file is opened and read, such as specifying whether the file should be opened in read mode, write mode, or both.
        :type flag: FDFlag
        :param rootFlag: The `rootFlag` parameter in the `read` method is a boolean flag that determines
        whether the root directory should be considered when reading files.
        :param encoding: The `encoding` parameter in the `read` method specifies the character encoding
        to be used when reading the files. In this case, the default encoding is set to "utf-8"
        """
        extension_ = extension(ext)
        root = path(rootParam) if type(rootParam) is str  else path(ext.value)
        setTempFile: set[str] = set()
        for file in Reader.fileService.listFileExtensions(extension_, root, recursive=True):
            relpath = root + os.path.sep+file
            filename, content, dir = Reader.fileService.readFileDetail(
                relpath, flag, encoding)
            keyName = filename if not setTempFile else file
            setTempFile.add(keyName)
            self.values[relpath] = self.asset(keyName, content, dir)

        if issubclass_of(Template, self.asset):  # TODO the part when we can load
            if self.func != None:
                self.func(self.values[relpath])

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        """
        :param ext:
        :type ext: Extension

        :param flag:
        :type flag: FDFlag

        :param rootFlag: 

        :param encoding:
        """
        self.safeReader(*args)
        return self.values


class ThreadedReader(Reader):
    def __init__(self, asset: Asset = Asset, additionalCode: Callable[..., Any] = None) -> None:
        super().__init__(asset, additionalCode)
        self.thread: Thread

    def read(self, ext: Extension, flag: FDFlag, rootFlag: bool | str = True, encoding="utf-8"):
        self.thread = Thread(target=super().read, args=(
            ext, flag, rootFlag, encoding))
        self.thread.start()

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        self.safeReader(*args)
        return self

    def join(self):
        self.thread.join()
        return self.values


@_service.PossibleDep([FTPService])
class AssetService(_service.Service):
    @inject
    def __init__(self, fileService: FileService, securityService: SecurityService, configService: ConfigService) -> None:
        super().__init__()
        Reader.fileService = fileService

        self.fileService = fileService
        self.securityService = securityService
        self.configService = configService

        self.images: dict[str, Asset] = {}
        self.css: dict[str, Asset] = {}

        self.htmls: dict[str, HTMLTemplate] = {}
        self.pdf: dict[str, PDFTemplate] = {}
        self.sms: dict[str, SMSTemplate] = {}
        self.phone: dict[str, PhoneTemplate] = {}

    def build(self):
        self.images = Reader()(Extension.JPEG, FDFlag.READ_BYTES, AssetType.IMAGES.value)
        self.css = Reader()(Extension.CSS, FDFlag.READ, AssetType.HTML.value)

        htmlReader: ThreadedReader = ThreadedReader(HTMLTemplate, self.loadData)(
            Extension.HTML, FDFlag.READ)
        pdfReader: ThreadedReader = ThreadedReader(
            PDFTemplate)(Extension.PDF, FDFlag.READ_BYTES)
        smsReader: ThreadedReader = ThreadedReader(SMSTemplate)(
            Extension.SMS, FDFlag.READ, AssetType.SMS.value)
        phoneReader: ThreadedReader = ThreadedReader(PhoneTemplate)(
            Extension.PHONE, FDFlag.READ, AssetType.PHONE.value)

        self.htmls = htmlReader.join()
        self.pdf = pdfReader.join()
        self.sms = smsReader.join()
        self.phone = phoneReader.join()
        
    def loadData(self, html: HTMLTemplate):
        cssInPath = self.fileService.listExtensionPath(
            html.dirName, Extension.CSS)
        for cssPath in cssInPath:
            try:
                css_content = self.css[cssPath].content
                html.loadCSS(css_content)
            except KeyError as e:
                pass

        imagesInPath = self.fileService.listExtensionPath(
            html.dirName, Extension.JPEG)
        for imagesPath in imagesInPath:
            try:
                imageContent = self.images[imagesPath].content
                html.loadImage(imageContent)
            except KeyError as e:
                pass

    def exportRouteName(self,attributeName:str)-> list[str] | None:
        """
        images: IMAGE Template Key
        css: CSS Template Key
        htmls: HTML Template Key
        pdf: PDF Template Key
        sms: SMS Template Key
        phone: Phone Template Key
        """
        try:
            temp:dict[str,Asset] = self.__getattribute__(attributeName)
            if type(temp) is not dict:
                raise TypeError()
            return [route.name for route in temp.values()]
        except TypeError as e:
            return None
        except KeyError as e:
            return None
        
    def destroy(self): pass

    def encryptPdf(self, name):
        KEY=""
        self.pdf[name].encrypt(KEY)

    def decryptPdf(self, name):
        KEY=""
        self.pdf[name].decrypt(KEY)
