from configparser import ConfigParser, NoOptionError, NoSectionError
from enum import Enum
import os
import json
import sys
import pickle
import glob

# BUG file name must be a non null string


class FDFlag(Enum):
    READ = "r"
    READ_BYTES = "rb"
    CREATE = "x"
    APPEND = "a"
    WRITE = "w"
    WRITE_BYTES = "wb"


def getFd(path: str, flag: FDFlag, enc: str = "utf-8"):
    try:
        return open(path, flag.value, encoding=enc)
    except:
        return None


def readFileContent(path: str, flag: FDFlag, enc: str = "utf-8"):
    try:
        if flag != FDFlag.READ and flag != FDFlag.READ_BYTES:
            raise KeyError()  # need a better error
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
            fd.write(content)
            pass
        fd.close()

    except:
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


class JSONFile():
    pass


class ConfigFile():
    """
    ConfigParser for properties files
    """

    def __init__(self, propertiesFile: str) -> None:
        self.properties = propertiesFile
        self.config = ConfigParser(comment_prefixes='#', delimiters="=")
        self.config.read(self.properties)

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
