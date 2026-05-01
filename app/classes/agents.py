from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_groq import ChatGroq
from langchain_core.language_models import BaseChatModel
from app.classes.secrets import ChaCha20Poly1305SecretsWrapper
from app.models.agents_model import AgentModel
from app.models.llm_model import LLMProfileModel
from app.utils.helper import subset_model
from pydantic import SecretStr


def ChatAgentFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper)->BaseChatModel:
        api_key =lambda: credentials.to_plain()

        max_output_token = llmModel.max_output_tokens
        max_tokens = agentModel.max_tokens
        if max_output_token:
            max_tokens = max_output_token

        provider = llmModel.provider
        match provider:
            case 'anthropic': 
                return ChatAnthropic(
                    streaming=True,
                    model_name=agentModel.model,
                    max_retries=agentModel.max_retries,
                    temperature=agentModel.temperature,
                    top_p=agentModel.top_p,
                    top_k=agentModel.top_k,
                    timeout=agentModel.timeout,
                    effort=agentModel.effort,
                    anthropic_proxy=agentModel.proxy_url,
                    base_url=llmModel.base_url
                )
            
            case 'cohere': 
                return ChatCohere(
                    streaming=True,
                    temperature=agentModel.temperature,
                    model=agentModel.model,
                    cohere_api_key=SecretStr(api_key()),
                    timeout_seconds=agentModel.timeout, 
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
                    max_completion_tokens=max_tokens,
                    api_key=api_key,
                    base_url= base_url,
                    temperature=agentModel.temperature,
                    max_retries=agentModel.max_retries,
                    timeout=agentModel.timeout,
                    top_p=agentModel.top_p,
                    model=agentModel.model,
                    frequency_penalty=agentModel.frequency_penalty,
                    presence_penalty=agentModel.presence_penalty,
                    n=agentModel.n,
                    reasoning_effort=agentModel.effort,
                    openai_proxy=agentModel.proxy_url
            )
            
            case 'groq': 
                return ChatGroq(
                    streaming=True,
                    max_tokens=max_tokens,
                    max_retries=agentModel.max_retries,
                    timeout=agentModel.timeout,
                    n=agentModel.n,
                    api_key=api_key,
                    model=agentModel.model,
                    temperature=agentModel.temperature,
                    groq_proxy=agentModel.proxy_url,
                    reasoning_effort=agentModel.effort,
                    reasoning_format=agentModel.reasoning_format,
                    base_url=llmModel.base_url
                )
            
            case 'ollama': raise NotImplementedError()
    
   