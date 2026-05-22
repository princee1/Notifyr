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

MODEL_RANKINGS = {
    "openai": {"gpt-5-mini": 1, "gpt-4.1-mini": 2, "gpt-4o-mini": 3,
        "gpt-5-nano": 4, "gpt-4.1-nano": 5, "gpt-5": 6,"gpt-5.1": 7, "gpt-5.2": 8, "gpt-5.2-pro": 9,
        "o3-mini": 10, "o3-mini-high": 11, "o3-pro": 12,"o1-mini": 13, "o1-preview": 14, "o3-deep-research": 15,
        "o4-mini-deep-research": 16, "gpt-4o": 17,"gpt-4.1": 18, "gpt-3.5-turbo": 19,
        "gpt-realtime-mini": 20, "gpt-realtime": 21,"gpt-audio-mini": 22, "gpt-audio": 23,"gpt-oss-20b": 24, "gpt-oss-120b": 25},
    "anthropic": {"claude-3-5-haiku-20241022": 1,"claude-3-haiku-20240307": 2,"claude-3-5-sonnet-20240620": 3,
        "claude-3-5-sonnet-20241022": 4,"claude-3-7-sonnet-20250219": 5,"claude-sonnet-4-20250514": 6,"claude-sonnet-4.5-20251022": 7,
        "claude-3-sonnet-20240229": 8,"claude-3-opus-20240229": 9,
        "claude-opus-4-1-20250805": 10,"claude-opus-4.5-20251101": 11},
    "cohere": {"command-r7b": 1, "command-r": 2,"command-r-08-2024": 3, "command-a-03-2025": 4,
        "command-r-plus": 5, "command-r-plus-v1": 6,"command": 7, "command-text-v14": 8},
    "groq": {"llama-3.1-8b-instant": 1, "gemma-2-9b-it": 2,
        "qwen3-32b": 3, "mixtral-8x7b": 4,"llama3-8b-8192": 5, "llama-3.3-70b-versatile": 6,
        "llama3-70b-8192": 7,"deepseek-r1-distill-llama-70b": 8,"whisper-large-v3": 9},
    "deepseek": {"deepseek-chat": 1, "DeepSeek-V3": 2,"DeepSeek-V3-0324": 3,"deepseek-r1-distill-llama-70b": 4,
        "DeepSeek-R1": 5, "DeepSeek-R1-Zero": 6},
    "gemini": {"gemini-2.0-flash-lite-preview-02-05": 1,"gemini-2.0-flash": 2,
        "gemini-2.0-flash-exp": 3,"gemini-1.5-pro": 4,"gemini-pro": 5},
    "ollama": {"llama3": 1}
}

#########################################################################################################
############################                                          ###################################
#########################################################################################################

class AgentNotAvailableError(BaseError):
    def __init__(self,status:ServiceStatus,reason:str,who:str=None):
        self.status = status
        self.reason = reason
        self.who = who

class AgentInputFormatNotSupportedError(BaseError):
    ...

class AgentContextDoesNotExistError(BaseError):
    ...

#########################################################################################################
############################                                          ###################################
#########################################################################################################


def ChatModelFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper,index:int=None)->BaseChatModel:
        api_key =lambda: credentials.to_plain()

        max_output_token = llmModel.max_output_tokens
        max_tokens = agentModel.generation.max_tokens
        if max_output_token:
            max_tokens = max_output_token
        
        provider = llmModel.provider

        profile = agentModel.profile.model_dump()
        profile = {**BASE_MODEL_PROFILE, **profile}

        if isinstance(agentModel.model,str):
            model = agentModel.model
        elif isinstance(agentModel.model,list):
            if not isinstance(index,int):
                raise ValueError('')
            model = agentModel.model[index]
        else:
            raise ValueError('')
            
        match provider:
            case 'anthropic': 
                return ChatAnthropic(
                    profile=profile,
                    streaming=True,
                    model_name=model,
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
                    model=model,
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
                    model=model,
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
                    model=model,
                    temperature=agentModel.generation.temperature,
                    groq_proxy=agentModel.generation.proxy_url,
                    reasoning_effort=agentModel.generation.effort,
                    reasoning_format=agentModel.generation.reasoning_format,
                    base_url=llmModel.base_url
                )
            case 'ollama': raise NotImplementedError()
    
def DynamicChatModelFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper):

    models = [ (MODEL_RANKINGS[llmModel.provider][m],i)  for i,m in enumerate(agentModel.model,) ]
    models = sorted(models,lambda t:t[0])
    chatModels = []
    for (_,index) in models: chatModels.append(ChatModelFactory(agentModel,llmModel,credentials,index))
    basic_chat_model = models[len(models)//2]
        
    @wrap_model_call
    async def dynamic_model_selection(request:ModelRequest,handler)->ModelResponse:
        return await handler(request.override(model=basic_model))
    
    return dynamic_model_selection,basic_chat_model