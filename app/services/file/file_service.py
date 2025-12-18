from pathlib import PurePath
from app.definition._service import BaseService,Service,AbstractServiceClass
from typing import Literal
from app.services.config_service import ConfigService
from app.utils.globals import DIRECTORY_SEPARATOR
from app.utils.fileIO import FDFlag, get_file_info, is_file, readFileContent,listFilesExtension,listFilesExtensionCertainPath, getFileOSDir, getFilenameOnly
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
    
    def soft_get_filename(self,path:str):
        if not self.soft_is_file(path):
            raise ValueError('Can only check if it is a file')
    
        return PurePath(path).name

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

    def file_matching(self,path,pattern:str):
        if not pattern:
            return True
        return PurePath(path).match(pattern)

    def root_to_path_matching(self,path_list:list[str], path:str,ext:str,sep=DIRECTORY_SEPARATOR,pointer:PointerIterator=None):
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
                if self.file_matching(f,f"{cursor}*{ext}"):
                    files.append(f)
                
            set_paths.difference_update(files)

        return files

    def get_extension(self,path:str)->str:
        return PurePath(path).suffix

    def soft_is_file(self,path:str):
        return self.get_extension(path) != ''

    def html_minify(self,input:bytes|str):
        import htmlmin

        input_type = type(input)
        if input_type == bytes:
            input = input.decode()
        
        return htmlmin.minify(input,False,True,True,).encode()
        
