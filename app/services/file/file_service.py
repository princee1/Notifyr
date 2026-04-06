import math
from pathlib import PurePath
from app.definition._service import BaseService,Service,AbstractServiceClass
from typing import Literal, Union
from app.services.config_service import ConfigService
from app.utils.globals import DIRECTORY_SEPARATOR
from app.utils.fileIO import FDFlag, get_file_info, is_file, readFileContent,listFilesExtension,listFilesExtensionCertainPath, getFileOSDir, getFilenameOnly
from app.utils.helper import PointerIterator
import base64
import os
import hashlib
from app.utils.tools import RunInThreadPool
from app.utils.helper import b64_encode

BytesSize= Literal['kb','mb','b']

BYTES_UNITS = {
    'b': 1,
    'kb': 1024,
    'mb': 1024 * 1024,
}

@Service()
class FileService(BaseService,):
    # TODO add security layer on some file: encription,decryption
    # TODO add file watcher
    
    def __init__(self,configService:ConfigService) -> None:
        super().__init__()
        self.configService = configService

    @RunInThreadPool
    def download_file(self, file_path: str, content: Union[str, bytes]) -> str:
        """
        Saves content to the specified file_path. 
        Works in both Docker and Host environments provided the path is accessible.
        """
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            if os.path.exists(file_path):
                raise FileExistsError(f'File already exists: {file_path}')

            data_to_write = content.encode('utf-8') if isinstance(content, str) else content

            with open(file_path, 'wb') as f:
                f.write(data_to_write)
                
            return file_path

        except PermissionError as e:
            raise PermissionError(f"Permission denied writing to '{file_path}'") from e
        except IsADirectoryError:
            raise IsADirectoryError(f"The path '{file_path}' is a directory, not a file.")
        except FileExistsError as e:
            raise e
        except OSError as e:
            raise OSError(f"An unexpected error occurred while downloading file to '{file_path}': {str(e)}")
        
    def delete_file(self, file_path: str) -> bool:
        """
        Deletes a file at the given path.
        """
        if not file_path:
            raise ValueError("File path cannot be empty.")

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Cannot delete: The file '{file_path}' does not exist.")

            if os.path.isdir(file_path):
                raise IsADirectoryError(f"Cannot delete: '{file_path}' is a directory. Use a directory removal method instead.")

            os.remove(file_path)
            return True

        except PermissionError as e:
            raise PermissionError(f"Permission denied deleting '{file_path}'. Ensure the application has write access.") from e
        except (FileNotFoundError , IsADirectoryError) as e:
            raise e
        except OSError as e:
            raise OSError(f"Error deleting file '{file_path}': {str(e)}")

    def readFileDetail(self, path, flag:FDFlag, enc="utf-8"):

        filename  = getFilenameOnly(path)
        content = readFileContent(path, flag, enc)
        dirName = getFileOSDir(path)

        return filename,content,dirName

    def bytes_conversion(self, size: int | float, _from: BytesSize, to: BytesSize):
        if size is None:
            return 0
        
        _from = _from.lower()
        to = to.lower()
        
        if _from not in BYTES_UNITS or to not in BYTES_UNITS:
            raise ValueError("'_from' and 'mode' must be one of 'b', 'kb', 'mb'")
        
        if _from == to:
            return math.ceil(size)

        size_bytes = float(size) * BYTES_UNITS[_from]
        target_value = size_bytes / BYTES_UNITS[to]

        if to == 'b':
            return int(target_value)
        return math.ceil(target_value)
        

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
                
    @RunInThreadPool
    def compute_sha256(self,file_obj,shrink:bool=True) -> str:
        """
        Compute SHA-256 hash of file.
        
        Args:
            file_obj: File object to hash
            shrink: If True, return base64-encoded hash (~44 chars, 31% smaller).
                    If False, return hex-encoded hash (64 chars).
                    
        Returns:
            Hash as string (base64 if shrink=True, hex if shrink=False)
        """
        
        hasher = hashlib.sha256()
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
        file_obj.seek(0)
        sha = hasher.hexdigest()
        if shrink:
            # Base64 encoding: 44 chars vs 64 hex chars (~31% reduction)
            return b64_encode(sha,True).rstrip('=')
        else:
            # Standard hex encoding: 64 characters
            return  sha