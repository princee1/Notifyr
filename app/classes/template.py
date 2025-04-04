
from enum import Enum
from typing import Any
from bs4 import BeautifulSoup, PageElement, Tag, element
from app.definition._error import BaseError
from app.classes.schema import MLSchemaBuilder
from app.utils.helper import strict_parseToBool, flatten_dict
from app.utils.validation import CustomValidator
# import fitz as pdf
from cerberus import DocumentError, SchemaError
from googletrans import Translator
import os
import re
from app.utils.prettyprint import printJSON
from cerberus import schema_registry


class XMLLikeParser(Enum):
    HTML = "html.parser"
    LXML = "lxml"
    XML ="xml"


# ============================================================================================================
ROUTE_SEP = "-"
VALIDATION_CSS_SELECTOR = "head > validation"
VALIDATION_REGISTRY_SELECTOR = "validation-registry"
def BODY_SELECTOR(select): return f"body {select}"
# ============================================================================================================


class TemplateNotFoundError(BaseError):
    ...

class TemplateBuildError(BaseError):
    ...

class TemplateValidationError(BaseError):
    ...

class SchemaValidationError(BaseError):
    ...

class SkipTemplateCreationError(BaseError):
    ...
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
        self.ignore=False


class Template(Asset):
    LANG = None

    def __init__(self, filename: str, content: str, dirName: str) -> None:
        super().__init__(filename, content, dirName)
        self.keys: list[str] = []
        self.translator = Translator(['translate.google.com', 'translate.google.com'])
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



class MLTemplate(Template):

    DefaultValidatorConstructorParamValues = {
        "require_all": True,
        "ignore_none_values": False,
        "allow_unknown": False,
        "purge_readonly": False,
        "purge_unknown": False,
    }

    def __init__(self, filename: str, content: str, dirName: str,extension:str,validation_selector:str) -> None:
        self.content_to_inject = None
        self.extension = extension
        self.validation_selector = validation_selector
        super().__init__(filename, content, dirName)
        self.ignore = self.filename.endswith(f".registry.{self.extension}")

    def _built_template(self,content):
        ...

    def inject(self, data: dict):
        try:
            content_html = str(self.content_to_inject)
            flattened_data = flatten_dict(data)
            for key in flattened_data:
                regex = re.compile(rf"{{{{{key}}}}}")
                content_html = regex.sub( str(flattened_data[key]), content_html)

            return self._built_template(content_html)
            
        except Exception as e:
            print(e.__class__)
            print(e.__cause__)
            print(e.args)  
            raise TemplateBuildError          

    def validate(self, document: dict):
        # TODO See: https://docs.python-cerberus.org/errors.html
        if self.schema == None or self.schema == {}:
            return True,document
        Validator = CustomValidator(self.schema)
        for property_, flag in HTMLTemplate.DefaultValidatorConstructorParamValues.items():
            Validator.__setattr__(property_, flag)
        try:
            document = Validator.normalized(document)
            if not Validator.validate(document):
                return False, Validator.errors
            return True, Validator.document
            # return self.Validator.normalized(document)
        except SchemaError as e:
            raise SchemaValidationError('Error of our document schema')
        except DocumentError as e:
            raise TemplateBuildError("Document is not a mapping of corresponding schema")
               
    def set_content(self,formatter):
        self.content_to_inject = self.bs4.prettify(formatter=formatter)

    def extractExtraSchemaRegistry(self):

        if self.validation_balise is None:
            return
        for registry in self.validation_balise.find_all(VALIDATION_REGISTRY_SELECTOR, recursive=False):
            registry: Tag = registry
            registry_key = registry.attrs["id"]
            schema = MLSchemaBuilder(registry).schema
            _hash = hash(schema)
            if _hash not in MLSchemaBuilder.CurrentHashRegistry.keys():
                MLSchemaBuilder.CurrentHashRegistry[_hash] = registry_key
                schema_registry.add(registry_key, schema)
            else:
                MLSchemaBuilder.HashSchemaRegistry[registry_key] = MLSchemaBuilder.CurrentHashRegistry[_hash]

    def extractValidation(self,):
        try:
            if self.validation_balise is None:
                return
            builder = MLSchemaBuilder(self.validation_balise)
            self.schema = builder.schema
            self.transform = builder.transform

            print(self.transform)
            self.keys = self.schema.keys()
            self.validation_balise.decompose()
        except SchemaError as e:
            # TODO raise another error and print the name of the template so the route will not be available
            printJSON(e.args[0])
            pass

    def load(self):
        self.bs4 = BeautifulSoup(self.content,self.parser)
        self.validation_balise = self.bs4.select_one(self.validation_selector)
        self.extractExtraSchemaRegistry()
        self.extractValidation()
        
    def translate(self, targetLang: str, text: str):
        if targetLang == Template.LANG:
            return text
        src = 'auto' if Template.LANG is None else Template.LANG
        translated = self.translator.translate(text, dest=targetLang, src=src)
        return translated.text

    def build(self,  data,target_lang):
        is_valid, data = super().build(target_lang, data)
        if not is_valid:
            raise TemplateValidationError(data)
        

class HTMLTemplate(MLTemplate):

    def __init__(self,filename:str,content:str,dirname:str):
        self.parser = XMLLikeParser.LXML.value

        super().__init__(filename,content,dirname,"html",VALIDATION_CSS_SELECTOR)
        self.images: list[tuple[str, str]] = []
        self.image_needed: list[str] = []
    
    def loadCSS(self, cssContent: str):  # TODO Try to remove any css rules not needed
        style = self.bs4.select_one("head > style")
        if style is None:
            head = self.bs4.select_one("head")
            style = Tag(name="style", attrs={"type": "text/css"})
            head.append(style)
        
        if style.string==None:
            style.string=""
        
        style.string += cssContent

    def exportText(self, content: str):
        bs4 = BeautifulSoup(content, XMLLikeParser.HTML.value)
        title = bs4.select_one("title")
        title.decompose()
        return bs4.get_text("\n", True)
    
    def extractImageKey(self,):
        img_element: set[Tag] = self.bs4.find_all("img")
        for img in img_element:
            src = img.attrs["src"]
            src = src.strip()
            if src is None or not src.startswith("cid:"):
                continue
            self.image_needed.append(src)

    def load(self):
        super().load()
        self.extractImageKey()
    
    def loadImage(self, image_path, imageContent: str):
        if image_path in self.image_needed:
            self.images.append((image_path, imageContent))

    def set_content(self,):
        super().set_content("html5")

    def build(self,data,target_lang):
        super().build(data,target_lang)
        content_html, content_text = self.inject(data)
        content_html = self.translate(target_lang, content_html)
        content_text = self.translate(target_lang, content_text)
        return True, (content_html, content_text)
    
    def _built_template(self,content):
        content_text = self.exportText(content)
        return content, content_text
    

class PDFTemplate(Template):
    def __init__(self, filename: str, dirName: str) -> None:
        super().__init__(filename, None, dirName)

    def pdf_to_xml(self):
        ...
    
    def xml_to_pdf(self):
        ...

class TWIMLTemplate(MLTemplate):

    def __init__(self, filename, content, dirName, extension, validation_selector):
        super().__init__(filename, content, dirName, extension, validation_selector)
        self.set_content()

    def _built_template(self,content):
        return content
    
    def set_content(self):
        response = self.bs4.select_one("Response")
        if not response:
            raise SkipTemplateCreationError('Response tag not given')
        self.content_to_inject = response.prettify(formatter="html")
    
    def build(self, data, target_lang):
        super().build(data, target_lang)
        body = self.inject(data)
        if False: 
            body = self.translate(target_lang,body) # TODO
        return True,body

class SMSTemplate(TWIMLTemplate):
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        self.parser =  XMLLikeParser.XML.value
        super().__init__(filename, content, dirName,"xml","validation")
    
    def set_content(self):
        message = self.bs4.select_one("Message")
        self.content_to_inject:str = message.text
        self.content_to_inject = self.content_to_inject.strip()

    def load_media(self, media: list[str]):
        raise NotImplementedError
        response = self.bs4.select_one("Response")
        if response is None:
            print("error")
            return
        for m in media:
            tag  = Tag(name="Media")
            tag.string = m
            response.append(tag)
        

class PhoneTemplate(TWIMLTemplate):
    def __init__(self, filename: str, content: str, dirName: str) -> None:
        self.parser =  XMLLikeParser.XML.value
        super().__init__(filename, content, dirName,"xml","validation")
        
####################### ########################

