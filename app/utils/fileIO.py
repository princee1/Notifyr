from enum import Enum
import pickle 
import json
import os
import sys

class FDFlag(Enum):
    READ = "r"
    READ_BYTES = "rb"
    CREATE="x"
    APPEND="a"
    WRITE="w"
    WRITE_BYTES="wb"


def getFd(path:str,flag:FDFlag,enc:str = "utf-8"):
    try:
        return open(path,flag.value,encoding=enc)
    except:
        return None


def readFileContent(path:str,flag:FDFlag,enc:str = "utf-8"):
    try:
        if flag != FDFlag.READ and flag != FDFlag.READ_BYTES:
            raise KeyError() # need a better erro
        fd = getFd(path,flag,enc)
        file_content = fd.read()
        fd.close()
        return file_content
    except:
        pass


