from typing import Any, List, Literal, Optional, Self
from pydantic import BaseModel, model_validator
from enum import Enum

class EmailMetaModel(BaseModel):
    Subject: str
    From: str
    To: str | List[str]
    CC: Optional[str] = None
    Bcc: Optional[str] = None
    replyTo: Optional[str] = None
    Priority: Literal['1', '3', '5'] = '1'
    Disposition_Notification_To:str|None = None
    Return_Receipt_To:str|None = None

    @model_validator(mode="after")
    def meta_validator(self)->Self:
        self.Disposition_Notification_To = None
        self.Return_Receipt_To = None
        return self


class EmailTemplateModel(BaseModel):
    meta: EmailMetaModel
    data: dict[str, Any]
    attachments: Optional[dict[str, Any]] = {}

class CustomEmailModel(BaseModel):
    meta: EmailMetaModel
    text_content: str
    html_content: str
    attachments: Optional[List[tuple[str, str]]] = []
    images: Optional[List[tuple[str, str]]] = []


class EmailSpamDetectionModel(BaseModel):
    recipient:str |List[str] | None
    body_plain:str |None
    body_html:str | None
    subject:str

    @model_validator(mode="after")
    def body_validator(self)->Self:
        if self.body_html == None and self.body_plain == None:
            raise ValueError('Plain body and Html body cannot both be null')
        return self


# =========================================================================         =======================================================

