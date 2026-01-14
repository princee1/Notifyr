from typing import TypedDict

class PromptToken(TypedDict):
    input:int
    output:int
    request_id:str
    issuer:str
    agent:str