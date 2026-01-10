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