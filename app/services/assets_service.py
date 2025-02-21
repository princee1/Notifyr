from fastapi import HTTPException,status

from app.definition._error import BaseError
from .config_service import ConfigService
from app.utils.fileIO import FDFlag
from app.classes.template import Asset, HTMLTemplate, PDFTemplate, SMSTemplate, PhoneTemplate, Template
from .security_service import SecurityService
from .file_service import FileService, FTPService
from app.definition import _service
from injector import inject
from enum import Enum
import os
from threading import Thread
from typing import Any, Callable, Literal, Dict
from app.utils.helper import issubclass_of

ROOT_PATH = "assets/"
DIRECTORY_SEPARATOR = '\\'
REQUEST_DIRECTORY_SEPARATOR = ':'

def path(x): return ROOT_PATH+x

class AssetNotFoundError(BaseError):
    ...

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
    
RouteAssetType = Literal['html', 'sms', 'phone']

def extension(extension: Extension): return f".{extension.value}"


class Reader():
    fileService: FileService

    def __init__(self, asset: type[Asset] = Asset, additionalCode: Callable = None) -> None:
        self.asset = asset
        self.values: Dict[str, Asset] = {}
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
        for file in self.fileService.listFileExtensions(extension_, root, recursive=True):
            relpath = root + os.path.sep+file
            filename, content, dir = self.fileService.readFileDetail(
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
@_service.ServiceClass
class AssetService(_service.Service):
    @inject
    def __init__(self, fileService: FileService, securityService: SecurityService, configService: ConfigService) -> None:
        super().__init__()
        self.fileService = fileService
        Template.LANG = configService.ASSET_LANG

        self.fileService:FileService = fileService
        self.securityService = securityService
        self.configService = configService

        self.images: dict[str, Asset] = {}
        self.css: dict[str, Asset] = {}

        self.html: dict[str, HTMLTemplate] = {}
        self.pdf: dict[str, PDFTemplate] = {}
        self.sms: dict[str, SMSTemplate] = {}
        self.phone: dict[str, PhoneTemplate] = {}

    def build(self):
        Reader.fileService = self.fileService
        self.images = Reader()(Extension.JPEG, FDFlag.READ_BYTES, AssetType.IMAGES.value)
        self.css = Reader()(Extension.CSS, FDFlag.READ, AssetType.HTML.value)

        htmlReader: ThreadedReader = ThreadedReader(HTMLTemplate, self.loadHTMLData)(
            Extension.HTML, FDFlag.READ)
        pdfReader: ThreadedReader = ThreadedReader(
            PDFTemplate)(Extension.PDF, FDFlag.READ_BYTES)
        smsReader: ThreadedReader = ThreadedReader(SMSTemplate)(
            Extension.SMS, FDFlag.READ, AssetType.SMS.value)
        phoneReader: ThreadedReader = ThreadedReader(PhoneTemplate)(
            Extension.PHONE, FDFlag.READ, AssetType.PHONE.value)

        self.html = htmlReader.join()
        self.pdf = pdfReader.join()
        self.sms = smsReader.join()
        self.phone = phoneReader.join()
        
        
    def loadHTMLData(self, html: HTMLTemplate):
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
                html.loadImage(imagesPath,imageContent)
            except KeyError as e:
                pass

    def exportRouteName(self,attributeName:RouteAssetType)-> list[str] | None:
        """
        html: HTML Template Key
        sms: SMS Template Key
        phone: Phone Template Key
        """
        try:
            if attributeName != "html" and  attributeName !="sms" and attributeName != "phone":
                raise AttributeError
            temp:dict[str,Asset] = getattr(self,attributeName)
            if type(temp) is not dict:
                raise TypeError()
            return list(temp.keys())
        except TypeError as e:
            return None
        except KeyError as e:
            return None
        except AttributeError as e:
            pass

    def asset_rel_path(self,path,asset_type):
        return f"{self.configService.ASSET_DIR}{asset_type}\\{path}"
        
    def verify_asset_permission(self,content,model_keys,assetPermission,options):
        
        permission = tuple(assetPermission)
        for keys in model_keys:
            s_content=content[keys]
            if type(s_content) == list:
                for c in s_content:
                    if type(c) == str:
                        if not c.startswith(permission):
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{c}] not allowed' })
                    
            elif type(s_content)==str:
                if not c.startswith(permission):
                            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail={'message':f'Assets [{s_content}] not allowed' })      
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={'message':'Entity not properly accessed'})
            
            for option in options:
                if not option(assetPermission):
                    return False

        return True
    
    def destroy(self): pass

    def encryptPdf(self, name):
        KEY=""
        self.pdf[name].encrypt(KEY)

    def check_asset(self,asset, allowed_assets:list[str]=None):
        if asset == None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail='Asset not specified')

        if allowed_assets == None and asset != "html" and  asset !="sms" and asset != "phone":
            raise AssetNotFoundError(asset)
        
        return asset in allowed_assets
            
