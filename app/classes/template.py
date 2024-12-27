
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup, PageElement, Tag, element
from utils.schema import HtmlSchemaBuilder
from utils.helper import strict_parseToBool, flatten_dict
from utils.validation import CustomValidator
# import fitz as pdf
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
        self.translator = Translator(
            ['translate.google.com', 'translate.google.com'])
        self.load()

    def inject(self, data:  dict) -> bool:
        """
        Inject the data into the template to build and return true if its valid
        """
        pass

    def load(self):
        """
        Build the template python representation from a template file
        """
        pass

    def build(self, lang, data) -> Any:
        """
        Build a representation of the template with injected, verified and translated value and return 
        a content output

        Override this function and call the super value
        """
        return self.validate(data)

    def translate(self, targetLang: str, text: str) -> str:
        """
        Translate the text value into another language
        """
        pass

    def validate(self, value: Any) -> bool | None | Exception:
        """
        Validate the data injected into the template
        """
        pass

    def exportText(self, content=None) -> str:
        """
        Only export the text
        """
        pass

    @property
    def routeName(self,): return self.name.replace(os.sep, ROUTE_SEP)


class HTMLTemplate(Template):

    ValidatorConstructorParam = [
        "require_all", "ignore_none_values", "allow_unknown", "purge_unknown", "purge_readonly"]
    DefaultValidatorConstructorParamValues = {
        "require_all": True,
        "ignore_none_values": False,
        "allow_unknown": False,
        "purge_readonly": False,
        "purge_unknown": False,
    }

    def __init__(self, filename: str, content: str, dirName: str) -> None:
        self.images: list[tuple[str, str]] = []
        self.image_needed: list[str] = []
        self.content_to_inject = None
        super().__init__(filename, content, dirName)

    def inject(self, data: dict):
        try:
            if not super().inject(data):
                # TODO Raise Error
                pass
            content_html = str(self.content_to_inject)
            flattened_data = flatten_dict()
            for key in flattened_data:
                regex = re.compile(rf"{{{{{key}}}}}")
                content_html = regex.sub(
                    str(flattened_data[key]), content_html)
            content_text = self.exportText(data)
            return content_html, content_text
        except KeyError as e:
            pass
        except:
            pass

    def validate(self, document: dict):
        # TODO See: https://docs.python-cerberus.org/errors.html
        if self.Validator == None:
            return True
        try:
            flag = self.Validator.validate(document)
            if not flag:
                raise DocumentError
            return True, self.Validator.document
            # return self.Validator.normalized(document)
        except DocumentError as e:
            # TODO raise a certain error
            print(self.Validator.errors)
            return False, self.Validator.errors

    def loadCSS(self, cssContent: str):  # TODO Try to remove any css rules not needed
        style = self.bs4.find("head > style")
        if style is None:
            head = self.bs4.find("head")
            new_style = PageElement()
            head.append(new_style)
            return
        style.replace(style.contents + cssContent)

    def loadImage(self, image_path, imageContent: str):
        if image_path in self.image_needed:
            self.images.append((image_path, imageContent))

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
            # for property_ in HTMLTemplate.ValidatorConstructorParam:
            #     self.set_ValidatorDefaultBehavior(property_)
            for property_, flag in HTMLTemplate.DefaultValidatorConstructorParamValues.items():
                self.Validator.__setattr__(property_, flag)
            self.keys = schema.keys()
            self.validation_balise.decompose()
            self.content_to_inject = self.bs4.prettify(formatter="html5")
            # TODO success
        except SchemaError as e:
            # TODO raise another error and print the name of the template so the route will not be available
            printJSON(e.args[0])
            pass

    def set_ValidatorDefaultBehavior(self, validator_property):
        try:
            flag = strict_parseToBool(
                self.validation_balise.attrs[validator_property])
            if flag is None:
                raise ValueError
            self.Validator.__setattr__(validator_property, flag)
        except KeyError:
            self.Validator.__setattr__(
                validator_property, HTMLTemplate.DefaultValidatorConstructorParamValues[validator_property])
        except ValueError:
            self.Validator.__setattr__(
                validator_property, HTMLTemplate.DefaultValidatorConstructorParamValues[validator_property])

    def exportText(self, content: str):
        bs4 = BeautifulSoup(content, XMLLikeParser.LXML.value)
        title = bs4.find("title", recursive=False)
        title.decompose()
        return bs4.get_text("\n", True)

    def save(self):
        pass

    def load(self):
        self.bs4 = BeautifulSoup(self.content, XMLLikeParser.LXML.value)
        self.validation_balise = self.bs4.select_one(VALIDATION_CSS_SELECTOR)
        self.extractExtraSchemaRegistry()
        self.extractValidation()
        self.extractImageKey()

    def translate(self, targetLang: str, text: str):
        if targetLang == Template.LANG:
            return text
        src = 'auto' if Template.LANG is None else Template.LANG
        translated = self.translator.translate(text, dest=targetLang, src=src)
        return translated.text

    def build(self, target_lang, data):
        is_valid, data = super().build(target_lang, data)
        if not is_valid:
            return False, data
        content_html, content_text = self.inject(data)
        content_html = self.translate(target_lang, content_html)
        content_text = self.translate(target_lang, content_text)
        return True, (content_html, content_text)

    def extractImageKey(self,):
        img_element: set[Tag] = self.bs4.find_all("img")
        for img in img_element:
            src = img.attrs["src"]
            src = src.strip()
            if src is None or not src.startswith("cid:"):
                continue
            self.image_needed.append(src)


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
####################### ########################

class TemplateNotFoundError(Exception):
    ...