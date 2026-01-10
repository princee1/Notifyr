from typing import ClassVar, List
from app.classes.mongo import BaseDocument
from app.utils.constant import MongooseDBConstant



class ToolModel(BaseDocument):
    ...

class AgentModel(BaseDocument):
    
    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION 
    provider: str
    memory:List[str] = []
    model: str
    tools: list[str] = []
    temperature: float = 0.7
    timeout:float = 20

    
    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION