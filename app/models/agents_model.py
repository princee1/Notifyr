from typing import ClassVar, List
from app.classes.mongo import BaseDocument
from app.utils.constant import MongooseDBConstant


class AgentModel(BaseDocument):
    
    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION 
    provider: str
    chats:List[str] = []
    default_model: str
    tools: list[str] = []
    default_temperature: float = 0.7

    
    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION