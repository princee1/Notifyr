from beanie import Document
from pydantic import Field
from pyparsing import Optional
from app.utils.constant import MongooseDBConstant

class BaseWorkflowModel(Document):
    alias:str
    description:Optional[str]|None = Field(None,description="A brief description of the workflow")
    class Settings:
        abstract = True


class NodeModel(BaseWorkflowModel):
    class Settings:
        name = MongooseDBConstant.NODE_COLLECTION

class EdgesModel(BaseWorkflowModel):
    class Settings:
        name = MongooseDBConstant.ARC_COLLECTION


class WorkFlowModel(BaseWorkflowModel):
    class Settings:
        name = MongooseDBConstant.WORKFLOW_COLLECTION