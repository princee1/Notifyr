from typing import ClassVar
from app.classes.mongo import BaseDocument
from app.utils.constant import MongooseDBConstant


class AgentModel(BaseDocument):
    
    _collection:ClassVar[str] = MongooseDBConstant.AGENT_COLLECTION 
    
    class Settings:
        name = MongooseDBConstant.AGENT_COLLECTION