from enum import Enum
from typing import Any, Self, overload
from aiohttp_retry import Callable
from bs4 import BeautifulSoup, PageElement, Tag, element
from app.definition._error import BaseError
from app.classes.schema import MLSchemaBuilder
from app.utils.constant import HTMLTemplateConstant
from app.utils.helper import strict_parseToBool, flatten_dict
from app.utils.tools import Time
from app.utils.validation import CustomValidator
# import fitz as pdf
from cerberus import DocumentError, SchemaError
from googletrans import Translator
import os
import re
from app.utils.prettyprint import printJSON
from cerberus import schema_registry
from jinja2 import Environment, Template as JJ2Template
from app.utils.transformer import transform,coerce


TRACKING_PIXEL_CODE = '''
{% if _tracking_url %}
  <img src="{{ _tracking_url }}" width="1" height="1" style="display:none;" alt="">
{% endif %}
'''

FOOTER_SIGNATURE_CODE='''
{% if _signature %}
  <div>{{ _signature }}</div>
{% endif %}
'''

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


class TemplateAssetError(BaseError):
    ...

class TemplateNotFoundError(BaseError):
    ...

class TemplateBuildError(BaseError):
    ...

class TemplateInjectError(BaseError):
    ...

class TemplateValidationError(BaseError):
    ...

class SchemaValidationError(BaseError):
    ...

class SkipTemplateCreationError(BaseError):
    ...

class TemplateFormatError(BaseError):
    ...

class TemplateCreationError(BaseError):
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
    
    @overload
    def __init__(self,filename:str, content:str, dirName:str) -> None:
        ...

    @overload
    def __init__(self,):
        ...
    
    def __init__(self,*args):
        if len(args) == 3:
            filename, content, dirName = args
            super().__init__(filename, content, dirName)
            self.translator = Translator(['translate.google.com', 'translate.google.com'])
            self.load()
        
        else:
            self.translator = Translator(['translate.google.com', 'translate.google.com'])

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

    def build(self, data, lang=None, validate=False) -> Any:
        """
        Build a representation of the template with injected, verified and translated value and return 
        a content output

        Override this function and call the super value
        """
        if validate:
            return self.validate(data)

    def translate(self, targetLang: str, text: str) -> str:
        """
        Translate the text value into another language
        """
        pass

    def validate(self, value: Any) -> Any | None | Exception:
        """
        Validate the data injected into the template
        """
        pass

    def exportText(self, content=None) -> str:
        """
        Only export the text
        """
        pass

    def clone(self)->Self:
        ...
    
    @property
    def routeName(self,): return self.name.replace(os.sep, ROUTE_SEP)



class MLTemplate(Template):
    _globals = {}

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
    

    def inject(self, data:dict, re_replace:Callable[[str],str]=None):
        #return super().inject(data, re_replace)
        env = Environment()
        
        env.filters['sub_url'] = lambda v:v if re_replace == None else re_replace 
        # for t in self.transform.values():
        #     if t not in transform:
        #         raise TemplateInjectError()
        #     env.filters[t] = transform[t]
        env.filters.update(transform)
        env.filters.update(coerce)

        env.globals.update(self._globals)

        content_html = str(self.content_to_inject)
        try:
            template = env.from_string(content_html)
            template = template.render(**data)
            return self._built_template(template)
        except Exception as e:
            raise TemplateBuildError()
        
    if False:
        def inject(self, data: dict,re_replace:Callable[[str],str]=None)->str:
            try:
                content_html = str(self.content_to_inject)
                flattened_data = flatten_dict(data)
                for key in flattened_data:
                    regex = re.compile(rf"{{{{{key}}}}}")
                    value = str(flattened_data[key])
                    if key in self.transform:
                        transformers = self.transform[key]
                        if isinstance(transformers,list):
                            for t in transformers:
                                value = t(value)
                        else:
                            value=transformers(value)
                    
                    if re_replace:
                        value = re_replace(value)

                    content_html = regex.sub(value, content_html)

                return self._built_template(content_html)
                
            except Exception as e:
                print(e.__class__)
                print(e.__cause__)
                print(e.args)  
                raise TemplateBuildError          

    def _validate(self, document: dict):
        """See: https://docs.python-cerberus.org/errors.html"""
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
            builder = MLSchemaBuilder(self.validation_balise,self.filename)
            self.schema = builder.schema
            self.transform = builder.transform
            self.validation_balise.decompose()
        except SchemaError as e:
            raise SkipTemplateCreationError(self.filename,e.args[0])

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

    # def build(self,  data,target_lang,validate=False):
    #     ...
    
    def validate(self, value):
        is_valid, data = self._validate(value)
        if not is_valid:
            raise TemplateValidationError(data)
        return data

class HTMLTemplate(MLTemplate):

    @overload
    def __init__(self,filename:str,content:str,dirname:str):
        ...

    @overload
    def __init__(self,bs4:BeautifulSoup,schema:dict,transform:dict,images:list[tuple[str, str]]):
        ...

    def __init__(self,*args):
        if len(args) == 3:
            filename,content,dirname = args
            self.parser = XMLLikeParser.HTML.value
            super().__init__(filename,content,dirname,"html",VALIDATION_CSS_SELECTOR)
            self.images: list[tuple[str, str]] = []
            self.image_needed: list[str] = []

        elif len(args):
            bs4, schema, transform, images = args
            self.parser = XMLLikeParser.HTML.value
            self.bs4: BeautifulSoup = BeautifulSoup(str(bs4), self.parser)
            self.schema = schema
            self.transform = transform
            self.images = images


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

    def build(self,data:dict,target_lang=None,re_replace=None,validate=False,bs4=False,tracking_url=None,signature=None):

        if len(HTMLTemplateConstant.values.intersection(data.keys())) > 0: 
            raise TemplateInjectError("Data contains reserved keys: {}".format(HTMLTemplateConstant.values))
        
        if validate:
            data = super().build(data,target_lang,validate)
        
        if tracking_url:
            data[HTMLTemplateConstant._tracking_url] = tracking_url

        if signature:
            data[HTMLTemplateConstant._signature] = signature[1]

        content_html, content_text = self.inject(data,re_replace=re_replace)
        if not target_lang or target_lang == Template.LANG:
            if bs4:
                content_html = str(BeautifulSoup(content_html, self.parser).select("body")[0])
            return True, (content_html, content_text)
        content_html = self.translate(target_lang, content_html)
        if bs4:
            content_html = BeautifulSoup(content_html, self.parser).select("body")[0]
        content_text = self.translate(target_lang, content_text)
        return True, (content_html, content_text)
    
    def _built_template(self,content):
        content_text = self.exportText(content)
        return content, content_text

    def add_tracking_pixel(self):
        """
        Add a tracking pixel to the HTML content.

        Args:
            tracking_url (str): The URL of the tracking pixel.
        """
        if not hasattr(self, 'bs4') or not self.bs4:
            raise TemplateCreationError("HTML content is not loaded or initialized.")
        
        tracking_pixel_tag = self.bs4.new_tag("div", attrs={"style": "display:none;"},string=TRACKING_PIXEL_CODE)
        body_tag = self.bs4.select_one("body")
        if body_tag:
            body_tag.append(tracking_pixel_tag)
        else:
            raise TemplateFormatError("No <body> tag found in the HTML content.")
    
        #self.set_content()

    def add_signature(self):
        signature_content = ("\n"*5)+FOOTER_SIGNATURE_CODE
        self.update_footer(signature_content)
        #self.set_content()

    def add_unsubscribe_footer(self):
        self.update_footer()
        self.set_content()

    def update_footer(self,content: str = ""):
        footer = self.bs4.select_one('footer')
        if footer is None:
            footer = Tag(name="footer")
            html = self.bs4.select_one('html')
            if html:
                html.append(footer)
            else:
                raise TemplateFormatError("No <html> tag found in the HTML content.")
        
        if footer.string is None:
            footer.string = content
        else:
            footer.string += f"\n{content}"

    def set_to_email_tracking_link(self, content: str):
        body = self.bs4.select_one('body')
        if body:
            body.decompose()
        new_body = BeautifulSoup(content,self.parser)
        html = self.bs4.select_one("html")
        html.append(new_body)
        self.set_content()

    def clone(self)->Self:
        clone = HTMLTemplate(self.bs4,self.schema,self.transform,self.images) 
        Template.__init__(clone)
        return clone

    @property
    def body(self):
        body = self.bs4.select_one("body")
        if body == None:
            raise TemplateFormatError("No <body> tag found in the HTML content.")
        return str(body)
    

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
    
    def build(self, data, target_lang,validate=False):
        super().build(data, target_lang,validate)
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
    
    def set_content(self):
        super().set_content()
        self.content_to_inject='''<?xml version="1.0" encoding="UTF-8"?>\n'''+self.content_to_inject
        
####################### ########################

