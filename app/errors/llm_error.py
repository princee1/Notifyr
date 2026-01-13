from app.definition._error import BaseError

class LLMProviderDoesNotExistError(BaseError):
    def __init__(self, provider:str):
        super().__init__()
        self.provider = provider

class LLMModelNotPermittedError(BaseError):
    def __init__(self, provider:str,model:str,models:list[str]):
        super().__init__()
        self.provider = provider
        self.model = model
        self.models = models

class LLMModelMaxTokenExceededError(BaseError):
    def __init__(self,provider:str,agent_max_token:int,llm_max_token:int):
        super().__init__()
        self.provider = provider
        self.agentMaxToken = agent_max_token
        self.llm_max_token = llm_max_token