
from dataclasses import dataclass
from bs4 import BeautifulSoup
import fitz as pdf
from googletrans import Translator

@dataclass
class Template():
    content: str | bytes
    filename: str
    dirName:str
    keys: set[str]
    lang:str
    def __init__(self,filename:str,content:str,dirName:str,lang:str) -> None:
        self.filename = filename
        self.content = content
        self.lang = lang
        self.dirName = dirName


    def inject(self, data: dict):pass
    def load(self): pass
    def build(self): pass
    def translate(self): pass
    def clone(self):pass
    def exportText(self):pass

class HTMLTemplate(Template):
    def __init__(self, filename:str,content:str,dirName:str,lang:str) -> None:
        super().__init__(filename, content,dirName,lang)

    def loadCSS(self,css:str, priority:int):pass

class PDFTemplate(Template):

    def encrypt():pass

    def decrypt():pass


class SMSTemplate(Template):pass

class PhoneTemplate(Template): pass