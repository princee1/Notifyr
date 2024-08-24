
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup, PageElement, Tag, element
from utils.schema import HtmlSchemaBuilder
from utils.helper import strict_parseToBool
from utils.validation import CustomValidator
import fitz as pdf
from cerberus import DocumentError, SchemaError
#from googletrans import Translator
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

    def translate(self, targetLang:str):
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

    def clone(self):
        """
        Copy the template in a ready state to be able to translate or add things to it
        """
        pass

    @property
    def routeName(self,): return self.name.replace(os.sep, ROUTE_SEP)


class HTMLTemplate(Template):

    ValidatorConstructorParam = ["require_all","ignore_none_values","allow_unknown","purge_unknown","purge_readonly"]
    DefaultValidatorConstructorParamValues = {} # TODO if i need to setup default value

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
        # TODO See: https://docs.python-cerberus.org/errors.html
        if self.Validator == None:
            return True
        try:
            flag = self.Validator.validate(document)
            if not flag:
                raise DocumentError
            return self.Validator.document
            # return self.Validator.normalized(document)
        except DocumentError as e:
            #TODO raise a certain error
            print(self.Validator.errors)
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
            for property_ in HTMLTemplate.ValidatorConstructorParam:
                self.set_ValidatorDefaultBehavior(property_)
            self.keys = schema.keys()
            self.validation_balise.decompose()
            #TODO success
        except SchemaError as e:
            #TODO raise another error and print the name of the template so the route will not be available
            printJSON(e.args[0])
            pass

    def set_ValidatorDefaultBehavior(self,validator_property):
        try:
            flag = strict_parseToBool(self.validation_balise.attrs[validator_property])
            if flag is None:
                raise ValueError
            self.Validator.__setattr__(validator_property,flag)
        except KeyError:
            self.Validator.__setattr__(validator_property,True)
        except ValueError:
            self.Validator.__setattr__(validator_property,True)

    def exportText(self):
        pass

    def save(self):
        pass

    def load(self):
        self.validation_balise = self.bs4.select_one(VALIDATION_CSS_SELECTOR)
        self.extractExtraSchemaRegistry()
        self.extractValidation()

    def translate(self):
        pass

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
