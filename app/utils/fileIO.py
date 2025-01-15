from configparser import ConfigParser, NoOptionError, NoSectionError
from dataclasses import dataclass
from enum import Enum
import os
import sys
import json
import pickle
import glob
from typing import Any, Literal, overload
from utils.question import ask_question, FileInputHandler
# BUG file name must be a non null string


class FDFlag(Enum):
    READ = "r"
    READ_BYTES = "rb"
    CREATE = "x"
    APPEND = "a"
    WRITE = "w"
    WRITE_BYTES = "wb"


def inputFilePath(message:str,instruction ="(Press CTRL-C to quit)",isDirectory=False):
    return ask_question([FileInputHandler(message,'location',isDir=isDirectory)])['location']

def getFd(path: str, flag: FDFlag, enc: str = "utf-8"):
    try:
        return open(path, flag.value, encoding=enc)
    except:
        return None


def exist(path):
    return getFd(path, FDFlag.READ) != None


def readFileContent(path: str, flag: FDFlag, enc: str = "utf-8"):
    try:
        if flag != FDFlag.READ and flag != FDFlag.READ_BYTES:
            raise KeyError()  #NOTE need a better error
        fd = getFd(path, flag, enc)
        file_content = fd.read()
        fd.close()
        return file_content
    except:
        return None


def writeContent(path: str, content, flag: FDFlag, enc: str = "utf-8"):
    try:
        fd = getFd(path, flag, enc)
        if fd.writable():
            if isinstance(content,(dict,list)):
                content = json.dumps(content)
            fd.write(content)
        fd.close()

    except Exception as e:
        print(e)
        pass


def listFilesExtension(extension: str, root=None, recursive: bool = False):
    if root != None and not os.path.isdir(f"{os.path.curdir}/{root}"):
        raise OSError

    return glob.glob(f"**/*{extension}", root_dir=root, recursive=recursive)


def listFilesExtensionCertainPath(path: str, extension: str):
    if not os.path.isdir(path):
        path = os.path.dirname(path)
        # WARNING:
    path: str = os.path.relpath(path)  # ensure its a relative path
    path_list: list[str] = path.split(os.path.sep)
    paths = []
    currPath = ""

    for p in path_list:
        currPath += p+f"{os.path.sep}"
        paths.append(currPath)

    results = []
    for p in paths:
        results.extend(listFilesExtension(extension, p))

    return results


def getFileDir(path: str):
    if not os.path.isfile(path):
        raise OSError
    return os.path.dirname(path)


def getFilenameOnly(path: str):
    return os.path.split(path)[1]


@dataclass
class File:
    file: str
    data: Any = None
    loaded: bool = False
    
    def __init__(self, file: str, from_data: Any=None):
        self.file = file
        self.load(from_data)

    def load(self, from_data: Any=None):
        ...

    def save(self):
        ...

    def clear(self):
        ...

    def write_raw(self, content, flag: Literal[FDFlag.WRITE, FDFlag.WRITE_BYTES] = FDFlag.WRITE):
        writeContent(self.file, content, flag)

    @property
    def exists(self):
        return exist(self.file)
    


class JSONFile(File):

    def __init__(self, jsonFilename, from_data=None):
        super().__init__(jsonFilename, from_data)

    def load(self, from_data=None):
        super().load(from_data)
        if not self.exists and from_data is None:
            return 

        if from_data != None:
            self.data = from_data
            self.loaded = True
            self.save()
            return 

        fd = getFd(self.file, FDFlag.READ)

        if fd is not None:
            try:
                self.data = json.load(fd)
                self.loaded = True
            except:
                # BUG might be better : self.data = None
                self.data = {}
                self.loaded = False
                ...
        
        return

    def save(self):
        if not self.loaded:
            return
        fd = getFd(self.file, FDFlag.WRITE)
        json.dump(self.data, fd)

    def clear(self):
        self.data = {}
        self.save()


class ConfigFile(File):
    """
    ConfigParser for properties files
    """

    def __init__(self, propertiesFile: str) -> None:
        super().__init__(propertiesFile)

    def load(self):
        self.config = ConfigParser(comment_prefixes='#', delimiters="=")
        self.config.read(self.file)
        pass

    def getValue(self, option, section):
        try:
            return self.config.get(option=option, section=section)
        except NoOptionError:
            return None
        except NoSectionError:
            return None

    def addValue(self, option, value, section):
        try:
            value = {option: value}
            self.config.read_dict({section: value})
            self.save()
        except NoOptionError as e:
            ...
        except NoSectionError as e:
            ...

    def setValue(self, option, value, section):
        try:
            self.config.set(section, option, value)
            self.save()
        except NoOptionError as e:
            ...
        except NoSectionError as e:
            ...

    def deleteValue(self, option, section):
        try:
            self.config.remove_option(section, option)
            self.save()
        except NoOptionError as e:
            ...
        except NoSectionError as e:
            ...

    def save(self):
        """
        It saves the config file.
        """
        file_descriptor = getFd(self.properties, FDFlag.WRITE)
        if file_descriptor is not None:
            self.config.write(file_descriptor)

    pass


class PickleFile(File):
    ...