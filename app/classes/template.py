
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup
import fitz as pdf
from googletrans import Translator
import os


class Parser(Enum):
    HTML= "html.parser"
    LXML = "lxml"


ROUTE_SEP= "-"


class Asset():
    def __init__(self,filename:str,content:str,dirName:str) -> None:
        super().__init__()
        self.filename = filename
        self.content = content
        self.dirName = dirName
        self.name = self.filename.split(".")[0]
    pass

class Template(Asset):
    LANG = None
    def __init__(self,filename:str,content:str,dirName:str) -> None:
        super().__init__(filename,content,dirName)
        self.keys:list[str] = []


    def inject(self, data:  dict):pass
    def load(self): pass
    def build(self): pass
    def translate(self): pass
    def exportText(self):pass

    @property
    def routeName(self,): return self.name.replace(os.sep,ROUTE_SEP)

class HTMLTemplate(Template):
    def __init__(self, filename:str,content:str,dirName:str) -> None:
        super().__init__(filename, content,dirName)
        self.bs4 = BeautifulSoup(self.content,Parser.LXML.value)
        self.validation:dict[str,str] = {}


    def inject(self, data: dict):
        return super().inject(data)

    def loadCSS(self,cssFiles: list[str]): pass


    def loadImage(self,image): pass

    def extractValidation(self,): pass

class PDFTemplate(Template): 
    def __init__(self, filename:str,content:str,dirName:str) -> None:
        super().__init__(filename, content,dirName)


    def encrypt(self, key:str):pass

    def decrypt(self,key:str):pass

class SMSTemplate(Template):
    def __init__(self, filename:str,content:str,dirName:str) -> None:
        super().__init__(filename, content,dirName)

class PhoneTemplate(Template):
    def __init__(self, filename:str,content:str,dirName:str) -> None:
        super().__init__(filename, content,dirName)
