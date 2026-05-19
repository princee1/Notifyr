from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_groq import ChatGroq
from langchain_core.language_models import BaseChatModel
from app.classes.secrets import ChaCha20Poly1305SecretsWrapper
from app.definition._error import BaseError
from app.definition._service import ServiceStatus
from app.models.odm.agents_model import AgentModel
from app.models.llm_model import LLMProfileModel
from app.utils.helper import subset_model
from pydantic import SecretStr
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse


BASE_MODEL_PROFILE = {
    'image_outputs':False,
    'audio_outputs':False,
    'video_outputs':False,
    'image_tool_message':False,
    'pdf_tool_message':False,
    'open_weights':False

}


class AgentNotAvailableError(BaseError):
    def __init__(self,status:ServiceStatus,reason:str,who:str=None):
        self.status = status
        self.reason = reason
        self.who = who

class AgentInputFormatNotSupportedError(BaseError):
    ...


def ChatModelFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper)->BaseChatModel:
        api_key =lambda: credentials.to_plain()

        max_output_token = llmModel.max_output_tokens
        max_tokens = agentModel.generation.max_tokens
        if max_output_token:
            max_tokens = max_output_token
        
        provider = llmModel.provider

        profile = agentModel.profile.model_dump()
        profile = {**BASE_MODEL_PROFILE, **profile}
        
        match provider:
            case 'anthropic': 
                return ChatAnthropic(
                    profile=profile,
                    streaming=True,
                    model_name=agentModel.model,
                    max_retries=agentModel.generation.max_retries,
                    temperature=agentModel.generation.temperature,
                    top_p=agentModel.generation.top_p,
                    top_k=agentModel.generation.top_k,
                    timeout=agentModel.generation.timeout,
                    effort=agentModel.generation.effort,
                    anthropic_proxy=agentModel.generation.proxy_url,
                    base_url=llmModel.base_url
                )
            case 'cohere': 
                return ChatCohere(
                    streaming=True,
                    profile=profile,
                    temperature=agentModel.generation.temperature,
                    model=agentModel.model,
                    cohere_api_key=SecretStr(api_key()),
                    timeout_seconds=agentModel.generation.timeout, 
                    base_url=llmModel.base_url
                )
            case 'deepseek'| 'openai' | 'gemini':
                match provider:
                    case 'deepseek':
                        base_url = llmModel.base_url or "https://api.deepseek.com"
                    case 'gemini':
                        base_url= llmModel.base_url or "https://generativelanguage.googleapis.com/v1beta"
                    case _:
                        base_url = llmModel.base_url or None
                return ChatOpenAI(
                    streaming=True,
                    profile=profile,
                    stream_usage=True,
                    max_completion_tokens=max_tokens,
                    api_key=api_key,
                    base_url= base_url,
                    temperature=agentModel.generation.temperature,
                    max_retries=agentModel.generation.max_retries,
                    timeout=agentModel.generation.timeout,
                    top_p=agentModel.generation.top_p,
                    model=agentModel.model,
                    frequency_penalty=agentModel.generation.frequency_penalty,
                    presence_penalty=agentModel.generation.presence_penalty,
                    n=agentModel.generation.n,
                    reasoning_effort=agentModel.generation.effort,
                    openai_proxy=agentModel.generation.proxy_url
            )
            case 'groq': 
                return ChatGroq(
                    profile=profile,
                    streaming=True,
                    max_tokens=max_tokens,
                    max_retries=agentModel.generation.max_retries,
                    timeout=agentModel.generation.timeout,
                    n=agentModel.generation.n,
                    api_key=SecretStr(api_key()),
                    model=agentModel.model,
                    temperature=agentModel.generation.temperature,
                    groq_proxy=agentModel.generation.proxy_url,
                    reasoning_effort=agentModel.generation.effort,
                    reasoning_format=agentModel.generation.reasoning_format,
                    base_url=llmModel.base_url
                )
            case 'ollama': raise NotImplementedError()
    
def DynamicChatModelFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper):

    advance_model = ChatModelFactory()
    basic_model = ChatModelFactory()

    @wrap_model_call
    async def dynamic_model_selection(request:ModelRequest,handler)->ModelResponse:

        return await handler(request.override(model=basic_model))

    
    return dynamic_model_selection,advance_model