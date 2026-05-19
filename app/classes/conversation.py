from typing import List, Literal, NamedTuple, Optional, TypedDict, Union, get_args
from time import time
from pydantic import BaseModel, Field
from app.utils.helper import generateId

# MIME type definitions by category
FileMime = Literal['pdf', 'docx', 'pptx', 'csv', 'xlsx', 'txt', 'json', 'xml', 'yaml']
ImageMime = Literal['jpeg', 'jpg', 'png', 'gif', 'webp', 'svg']
TextMime = Literal['plain', 'markdown']

file_mime_list = set(get_args(FileMime))
image_mime_list = set(get_args(ImageMime))
text_mime_list = set(get_args(TextMime))

class ContentBlock(BaseModel):
    mode:Literal['file','text-plain','image']
    type:Literal['url','base64']
    value:str
    mime:Optional[Union[FileMime, ImageMime, TextMime]] = None
    
    def model_post_init(self, __context):
        """Validate and normalize content block."""
        self._validate()
    
    def _validate(self):
        """Validate mode, type, mime, and value combinations."""
        if self.type == 'base64':
            if not self.mime:
                raise ValueError(f"{self.mode} base64 type requires mime to be specified")

            match self.mode:
                case 'file':
                    if self.mime not in file_mime_list:
                        raise ValueError(f"File base64 mime must be one of {{pdf, docx, csv, pptx, xlsx, txt, json, xml, yaml}}, got '{self.mime}'")
                case 'image':
                    if self.mime not in image_mime_list:
                        raise ValueError(f"Image base64 mime must be one of {{jpeg, png, jpg, gif, webp, svg}}, got '{self.mime}'")
                case 'text-plain':
                    if self.mime not in text_mime_list:
                        raise ValueError(f"Text-plain base64 mime must be one of {{plain, markdown,}}, got '{self.mime}'")

        if self.type == 'url':
            if not self.value.startswith(('http://', 'https://')):
                raise ValueError("URL type requires value to start with http:// or https://")
        
    def export(self) -> dict:
        """Export as Langchain-compatible content block."""
        return self.exports(self.mode, self.type, self.value, self.mime)

    @staticmethod
    def exports(mode: str, type: str, value: str, mime: str | None) -> dict:
        """Create standardized Langchain multimodal content block."""
        temp = {'type':mode, type:value}
        if mime:
            match mode:
                case 'image':
                    temp['mime_type'] = f'image/{mime}'
                case 'file':
                    temp['mime_type'] = f'application/{mime}'
                case 'text-plain':
                    temp['mime_type'] = f'text/{mime}'
        return temp        



class ToolCalling(TypedDict):
    id:str
    args:dict
    name:str

class InvalidToolCalling(ToolCalling):
    error:str
    index:int

class Reasoning(TypedDict):
    index:int
    thought:str
    id:str


class Message(BaseModel):
    agent:str
    thread:str
    user:str
    prompt:str
    content_block:List[ContentBlock] = Field(default_factory=list)
    mess_id:str = Field(default_factory=lambda :generateId(0))
    send_at:float = Field(default_factory=time)
    
TOOL_CALLING_KEYS = {'id','args','name'}
invalid_tool_calling_keys = TOOL_CALLING_KEYS.union(['error','index'])

class Reply(BaseModel):
    text:str
    reply_id:str
    agent:str

    reasoning:List[Reasoning]
    tool_calling:List[ToolCalling]
    invalid_tool_calling:List[InvalidToolCalling]
    send_at:float = Field(default_factory=time)

class Token(TypedDict):
    input_token:int
    output_token:int

class Answer(TypedDict):
    text:str
    reply_id:str
    agent:str

    reasoning:List[Reasoning]
    tool_calling:List[ToolCalling]
    invalid_tool_calling:List[InvalidToolCalling]
    token: Token

class Thread(NamedTuple):
    agent:str
    conversation:str

def to_thread(thread:str,agent:str):
    return f"{thread}@{agent}"

def from_thread(thread:str)->Thread:
    t = thread.split('@')
    if not t or len(t) != 2:
        raise ...
    return Thread(*t)


