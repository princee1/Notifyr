
from dataclasses import dataclass


@dataclass
class Template():
    name:str
    content: str | bytes
    
    def inject(self, data: dict):pass

class HTMLTemplate():

    def __init__(self,filename:str) -> None:
        self.filename = filename
        self.name:str
        self.content:str
        pass
    pass

class PDFTemplate():
    pass

class SMSTemplate():
    pass