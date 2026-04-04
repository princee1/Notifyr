from typing import Literal
from app.definition._cost import Cost

TokenType = Literal['input','output']

class TokenCost(Cost):

    def __inner__init__(self, request_id, issuer):
        self.definition_name = 'Token'
        return super().__inner__init__(request_id, issuer)
    
    def purchase(self, model:str,provider:str,provider_id:str,token_type:TokenType,description:str,quantity:int=1):
        description = f"{provider}/{model}@{provider_id}:{token_type} - {description}"
        return super().purchase(description,1, quantity)

