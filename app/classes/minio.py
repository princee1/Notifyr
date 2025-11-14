from typing import Optional
from fastapi import Request
from pydantic import BaseModel


class ObjectS3ResponseModel(BaseModel):
        meta: Optional[list|dict] = []
        errors: Optional[list]=[]
        result: Optional[dict] ={}
        content: Optional[str] = ""


def key_setter(template:str,request:Request):
        return f"{template}/{request.query_params.get('version_id',None)}"