from fnmatch import fnmatch
from pathlib import PurePath
import traceback
from typing import Any, Literal
from app.definition._error import BaseError
from app.interface.timers import IntervalInterface
from app.utils.globals import DIRECTORY_SEPARATOR
from .config_service import AssetMode, ConfigService
from app.definition._service import GUNICORN_BUILD_STATE, BaseService,Service,AbstractServiceClass
from app.utils.fileIO import FDFlag, get_file_info, is_file, readFileContent, getFd, JSONFile, writeContent,listFilesExtension,listFilesExtensionCertainPath, getFileOSDir, getFilenameOnly
from ftplib import FTP, FTP_TLS
import git_clone as git
from app.utils.helper import PointerIterator

@Service()
class FileService(BaseService,):
    # TODO add security layer on some file: encription,decryption
    # TODO add file watcher
    def __init__(self,configService:ConfigService) -> None:
        super().__init__()
        self.configService = configService
        
    def readFileDetail(self, path, flag:FDFlag, enc="utf-8"):

        filename  = getFilenameOnly(path)
        content = readFileContent(path, flag, enc)
        dirName = getFileOSDir(path)

        return filename,content,dirName

    def build(self,build_state=-1):
        ...

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

    def is_file(self,path:str,allowed_multiples_suffixes=False,allowed_extensions:set|list=None):
        return is_file(path,allowed_multiples_suffixes,allowed_extensions)

    def get_file_dir(self,path:str,method:Literal['os','pure','custom']='os',sep=DIRECTORY_SEPARATOR):
        match method:
            case 'os':
                return getFileOSDir(path)
            case 'custom':
                return path.rsplit(sep, 1)[0] if "/" in path else ""
            case 'pure':
                return str(PurePath(path).parent)
            case _:
                raise ValueError(method)

    def simple_file_matching(self,path:str,root:str|tuple[str,...]=None,ext:str|tuple[str,...]=None):
        if root== None and ext==None:
            raise ValueError
        
        if root != None and ext == None:
            return  path.startswith(ext)

        if root == None and ext!= None:
            return path.endswith(ext)
        
        return path.startswith(root) and path.endswith(ext)

    def file_pattern_matching(self,path,pattern:str):
        return PurePath(path).match(pattern)

    def relative_file_matching(self,path_list:list[str], path:str,ext:str,sep=DIRECTORY_SEPARATOR,pointer:PointerIterator=None):
        cursor=""
        files = []
        try:
            set_paths = set(path_list)
        except TypeError as e :
            if pointer != None:
                set_paths = set([pointer.ptr(x).get_val() for x in path_list ])
            else:
                raise e
            
        for p in path.split(sep):
            cursor+=f"{p}{sep}"
            
            for f in set_paths:
                if self.file_pattern_matching(f,f"{cursor}*{ext}"):
                    files.append(f)
                
            set_paths.difference_update(files)

        return files

    def get_extension(self,path:str)->str:
        return PurePath(path).suffix

    def soft_is_file(self,path:str):
        return self.get_extension(path) == ''

@AbstractServiceClass()
class BaseFileRetrieverService(BaseService,IntervalInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService):
        super().__init__()
        self.configService = configService
        self.fileService = fileService
    
@Service()
class FTPService(BaseFileRetrieverService):
    def __init__(self, configService: ConfigService, fileService: FileService) -> None:
        super().__init__(configService,fileService)
        self.ftpClient: FTP
        pass

    def build(self, build_state = ...):
        if build_state != GUNICORN_BUILD_STATE:
            return
        
        if self.configService.ASSET_MODE != AssetMode.ftp:
            return
        
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

@Service()
class GitCloneRepoService(BaseFileRetrieverService):
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)
    
    def build(self, build_state = ...):
        if build_state != GUNICORN_BUILD_STATE:
            return
        
        if self.configService.ASSET_MODE != AssetMode.github:
            return
        

    def destroy(self,destroy_state=-1):
        return super().destroy()
    pass

