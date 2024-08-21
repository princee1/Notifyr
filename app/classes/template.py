
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup, PageElement, Tag, element
from utils.validation import HtmlSchemaBuilder, CustomValidator
import fitz as pdf
from cerberus import DocumentError, SchemaError
from googletrans import Translator
import os
import re
from utils.prettyprint import printJSON
from cerberus import schema_registry


class XMLLikeParser(Enum):
    HTML = "html.parser"
    LXML = "lxml"


# ============================================================================================================
ROUTE_SEP = "-"
VALIDATION_CSS_SELECTOR = "head > validation"
VALIDATION_REGISTRY_SELECTOR = "validation-registry"
def BODY_SELECTOR(select): return f"body {select}"
# ============================================================================================================
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

    def inject(self, data:  dict) -> bool:
        """
        Inject the data into the template to build and return true if its valid
        """
        tempKey = set(self.keys)
        dataKey = set(data.keys())
        if tempKey.difference(dataKey()) != 0:
            raise KeyError
        return self.validate(data)

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
            if not super().inject(data):
                # TODO Raise Error
                pass
            self.content = self.bs4.prettify(formatter="html5")
            # TODO inject
            self.bs4 = BeautifulSoup(self.content, XMLLikeParser.LXML.value)
        except KeyError as e:
            pass
        except:
            pass

    def recursiveInject(self,currKey, data):
        pass

    def validate(self, document: dict):
        if self.Validator == None:
            return True
        try:
            flag = self.Validator(document)
            self.Validator.errors
            return self.Validator.document
            valid_documents = [x for x in [self.Validator.validated(y) for y in documents]
                               if x is not None]
            return valid_documents
        except DocumentError as e:
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

    def extractExtraSchemaRegistry(self):

        if self.validation_balise is None:
            return
        for registry in self.validation_balise.find_all(VALIDATION_REGISTRY_SELECTOR, recursive=False):
            registry: Tag = registry
            registry_key = registry.attrs["id"]
            schema = HtmlSchemaBuilder(registry).schema
            _hash = hash(schema)
            if _hash not in HtmlSchemaBuilder.CurrentHashRegistry.keys():
                HtmlSchemaBuilder.CurrentHashRegistry[_hash] = registry_key
                schema_registry.add(registry_key, schema)
            else:
                HtmlSchemaBuilder.HashSchemaRegistry[registry_key] = HtmlSchemaBuilder.CurrentHashRegistry[_hash]
        
    def extractValidation(self,):
        try:
            if self.validation_balise is None:
                return
            schema = HtmlSchemaBuilder(self.validation_balise).schema
            self.Validator = CustomValidator(schema)
            try:
                self.Validator.require_all = self.validation_balise.attrs['require_all']
            except KeyError:
                self.Validator.require_all = True
            try:
                self.Validator.allow_unknown = self.validation_balise.attrs['allow_unknown']
            except KeyError:
                self.Validator.allow_unknown = True
            self.keys = schema.keys()
            self.validation_balise.decompose()
        except SchemaError as e:
            printJSON(e.args[0])
            pass

    def exportText(self):
        pass

    def save(self):
        pass

    def load(self):
        self.validation_balise = self.bs4.select_one(VALIDATION_CSS_SELECTOR)
        self.extractExtraSchemaRegistry()
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
