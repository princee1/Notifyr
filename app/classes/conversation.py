class ToolOutput:
    ...
class Message:
    agent:bool
    person:str
    time:int
    content:str

class Conversation:
    agent:str
    agent_name:str
    contact:str
    tools:list[ToolOutput]
    rating:float
    messages:list[Message]
    start_time:int
    end_time:int



