from dataclasses import asdict, dataclass
import json
from typing import Optional, TypedDict
import json


@dataclass
class SourceDescription:
    id:str
    source:str
    title:str
    document_name:str
    lang:Optional[str] = None
    description:Optional[str] = None
    document_id:Optional[str] = None

    def Save(self)->str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def From(source:str)->'SourceDescription':
        return SourceDescription(**json.loads(source))
    

class KGraphFacts(TypedDict):
    target_summary:str|None
    source_summary:str|None
    fact:str
    score:float
    source:list[SourceDescription]