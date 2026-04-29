from typing import Literal
from app.definition._cost import Cost
from app.classes.cost_definition import ProviderMultiplierCostDefinition,ModelMultiplierCostDefinition

TokenType = Literal['input','output']

class TokenCost(Cost):

    def __inner__init__(self, request_id, issuer):
        self.definition_name = 'Token'
        super().__inner__init__(request_id, issuer)
        self.provider_cost:ProviderMultiplierCostDefinition = self.costService.fetch_definition('providers',{})
        self.model_cost:ProviderMultiplierCostDefinition = self.costService.fetch_definition('models',{})

    def purchase(self, model:str,provider:str,provider_id:str,token_type:TokenType,description:str,quantity:int=1):
        description = f"{provider}/{model}@{provider_id}:{token_type} - {description}"
        factor = 1
        factor *= self.provider_cost.get(provider,1)
        factor *= self.model_cost.get(model,1)
        return super().purchase(description,factor, quantity)

