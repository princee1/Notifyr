
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup, PageElement,element
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

    def inject(self, data:  dict):
        tempKey = set(self.keys)
        dataKey = set(data.keys())
        if tempKey.difference(dataKey()) != 0:
            raise KeyError
         
    def load(self): pass

    def build(self, lang): pass

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
        try:
            super().inject(data)
        except KeyError as e: pass
        except: pass

    def loadCSS(self,cssContent: str): # TODO Try to remove any css rules not needed
        return 
        style = self.bs4.find("style")
        if style is None:
            head = self.bs4.find("head")
            new_style = PageElement()
            head.append(new_style)
            return 
        style.replace(style.contents+ cssContent)

    def loadImage(self,imageContent:str): 
        pass

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
