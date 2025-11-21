from app.definition._service import BaseMiniService, MiniService
from app.interface.llm_provider import LLMProvider
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.logger_service import LoggerService
from app.utils.constant import LLMProviderConstant
from openai import OpenAI,AsyncOpenAI


@MiniService()
class OpenAIProviderMiniService(BaseMiniService,LLMProvider):

    def __init__(self,configService:ConfigService,costService:CostService,loggerService:LoggerService):
        super().__init__(None,LLMProviderConstant.OPENAI)
        self.configService = configService
        self.loggerService = loggerService
        self.costService = costService
    

    def build(self, build_state = ...):
        self.client = OpenAI()
        