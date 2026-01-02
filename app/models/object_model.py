from typing import Any, Optional
from fastapi import Request
from pydantic import BaseModel
from .file_model import FileResponseUploadModel


class ObjectS3ResponseModel(BaseModel):
        meta: Optional[list|dict] = []
        errors: Optional[list]=[]
        result: Optional[dict] ={}
        content: Optional[str] = ""


def key_setter(template:str,request:Request):
        return f"{template}/{request.query_params.get('version_id',None)}"


class ObjectResponseUploadModel(FileResponseUploadModel):
        uploaded_files:list[str]
        errors: dict[str,Any]