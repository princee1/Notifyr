
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup, PageElement, Tag, element
from utils.validation import HtmlSchemaBuilder,CustomValidator
import fitz as pdf
from googletrans import Translator
import os
import re
from utils.prettyprint import printJSON


class XMLLikeParser(Enum):
    HTML = "html.parser"
    LXML = "lxml"


# ============================================================================================================
ROUTE_SEP = "-"
VALIDATION_CSS_SELECTOR = "head > validation"
def BODY_SELECTOR(select): return f"body {select}"
# ============================================================================================================


class Asset():
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__()
        self.filename = filename
        self.content = content
        self.dirName = dirName
        self.name = self.filename.split(".")[0]
        # BUG need to replace the path separator
        self.name.replace("\\", ROUTE_SEP)
        self.name.replace("/", ROUTE_SEP)


class Template(Asset):
    LANG = None

    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__(filename, content, dirName)
        self.keys: list[str] = []

    def inject(self, data:  dict):
        """
        Inject the data into the template to build 
        """
        tempKey = set(self.keys)
        dataKey = set(data.keys())
        if tempKey.difference(dataKey()) != 0:
            raise KeyError

    def load(self):
        """
        Build the template python representation from a template file
        """
        pass

    def build(self, lang, data):
        """
        Build a representation of the template with injected, verified and translated value and return 
        a content output
        """
        pass

    def translate(self, lang):
        """
        Translate the text value into another language
        """
        pass

    def validate(self):
        """
        Validate the data injected into the template
        """
        pass

    def exportText(self):
        """
        Only export the text
        """
        pass

    @property
    def routeName(self,): return self.name.replace(os.sep, ROUTE_SEP)


class HTMLTemplate(Template):
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__(filename, content, dirName)
        self.bs4 = BeautifulSoup(self.content, XMLLikeParser.LXML.value)
        self.load()

    def inject(self, data: dict):
        try:
            super().inject(data)
            self.content = self.bs4.prettify(formatter="html5")
            #TODO inject
            self.bs4 = BeautifulSoup(self.content, XMLLikeParser.LXML.value)
        except KeyError as e:
            pass
        except:
            pass

    def findAllKeys(self):
        pass

    def recursiveInject():
        pass

    def loadCSS(self, cssContent: str):  # TODO Try to remove any css rules not needed
        style = self.bs4.find("head > style")
        if style is None:
            head = self.bs4.find("head")
            new_style = PageElement()
            head.append(new_style)
            return
        style.replace(style.contents + cssContent)

    def loadImage(self, imageContent: str):
        pass

    def extractValidation(self,):
        validation = self.bs4.select_one(VALIDATION_CSS_SELECTOR)
        if validation is None:
            return
        schema = HtmlSchemaBuilder(validation).schema
        self.Validator = CustomValidator(schema)
        try:
            self.Validator.require_all = validation.attrs['require_all']
        except KeyError:
            self.Validator.require_all = True
        try:
            self.Validator.allow_unknown = validation.attrs['allow_unknown']
        except KeyError:
            self.Validator.allow_unknown = True
        self.keys = schema.keys()
        validation.decompose()

    def exportText(self):
        pass

    def save(self):
        pass

    def load(self):
        self.extractValidation()


class CustomHTMLTemplate(HTMLTemplate):
    pass


class PDFTemplate(Template):
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__(filename, content, dirName)

    def encrypt(self, key: str): pass

    def decrypt(self, key: str): pass


class SMSTemplate(Template):
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__(filename, content, dirName)


class PhoneTemplate(Template):
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__(filename, content, dirName)
