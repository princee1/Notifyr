from typing import Any
from beanie import Document
from pydantic import Field
from pyparsing import Optional
from app.utils.constant import MongooseDBConstant
import cerberus
from app.classes.celery import TaskTypeLiteral

####################################################                              ###########################################
####################################################                              ###########################################
class BaseWorkflowModel(Document):
    alias:str
    description:Optional[str]|None = Field(None,description="A brief description of the workflow")
    class Settings:
        abstract = True

####################################################                              ###########################################
####################################################                              ###########################################
class NodeModel(BaseWorkflowModel):
    
    class Settings:
        is_root = True
        name = MongooseDBConstant.NODE_COLLECTION

class TriggerNode(NodeModel):
    ...


class TaskNode(NodeModel):
    
    task_name:str
    retry:int = Field(1,ge=0,le=100)


class FreqWaitNode(NodeModel):
    task_type:TaskTypeLiteral
    task_option:dict[str,str|int|float|bool]


class PipeNode(NodeModel):
    ...

####################################################                              ###########################################
####################################################                              ###########################################
class EdgesModel(BaseWorkflowModel):
    class Settings:
        name = MongooseDBConstant.ARC_COLLECTION


class DirectNode(EdgesModel):
    ...

class ConditionEdge(EdgesModel):
    
    condition:dict[str,Any]

####################################################                              ###########################################
####################################################                              ###########################################
class WorkFlowModel(BaseWorkflowModel):
    class Settings:
        name = MongooseDBConstant.WORKFLOW_COLLECTION