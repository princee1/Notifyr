from typing import Any, ClassVar
from beanie import Document
from pydantic import Field
from pyparsing import Optional
from app.classes.mongo import BaseDocument
from app.utils.constant import MongooseDBConstant
import cerberus
from app.classes.celery import TaskTypeLiteral

####################################################                              ###########################################
####################################################                              ###########################################
class BaseWorkflowModel(BaseDocument):

    class Settings:
        abstract = True

####################################################                              ###########################################
####################################################                              ###########################################
class NodeModel(BaseWorkflowModel):
    
    _collection:ClassVar[str] = MongooseDBConstant.NODE_COLLECTION

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
    _collection:ClassVar[str] = MongooseDBConstant.EDGE_COLLECTION

    class Settings:
        name = MongooseDBConstant.EDGE_COLLECTION


class DirectNode(EdgesModel):
    ...

class ConditionEdge(EdgesModel):
    
    condition:dict[str,Any]

####################################################                              ###########################################
####################################################                              ###########################################
class WorkFlowModel(BaseWorkflowModel):
    class Settings:
        name = MongooseDBConstant.WORKFLOW_COLLECTION