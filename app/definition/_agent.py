from dataclasses import dataclass, field
import math
from typing import Callable, Dict, List, Literal, NamedTuple, Optional, TypedDict,Any, override
from langchain.agents.middleware.types import AgentState, ContextT, dynamic_prompt
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_groq import ChatGroq
from langchain_core.language_models import BaseChatModel
from app.classes.secrets import ChaCha20Poly1305SecretsWrapper
from app.definition._error import BaseError
from app.definition._service import ServiceStatus
from app.models.odm.agents_model import AgentModel,MIN_OF_MAX_INPUT_TOKEN
from app.models.odm.llm_model import LLMProfileModel
from app.utils.helper import subset_model
from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage,SystemMessage
from langchain.messages import ToolMessage
from langchain_core.messages.utils import count_tokens_approximately
from pydantic import SecretStr
from langchain.agents.middleware import Runtime, wrap_model_call, ModelRequest, ModelResponse
from langchain.agents.middleware import SummarizationMiddleware as BaseSummarizationMiddleware
from langgraph.graph.message import REMOVE_ALL_MESSAGES

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

FIRST_KEEP_MESSAGE = 3

COMPLEXITY_WEIGHT = (
    0.25,  # total_tokens
    0.25,  # last_user_tokens
    0.20,  # tool_calls
    0.10,  # summarized
    0.10,  # session_count
    0.10,  # retries,
    0.05   # message_depth
)

class MaxToken(NamedTuple):
    output:int | None
    input: int|None

def extract_max_tokens(agentModel:AgentModel, llmModel:LLMProfileModel):
    if llmModel.max_output_tokens != None and agentModel.generation.max_tokens == None:
        max_output_tokens = llmModel.max_output_tokens
    else:
        max_output_tokens = agentModel.generation.max_tokens
        
    if llmModel.max_input_tokens != None and agentModel.profile.max_inputs_token == None:
        max_inputs_token = llmModel.max_input_tokens
    else:
        max_inputs_token = agentModel.profile.max_inputs_token
    return MaxToken(max_output_tokens,max_inputs_token)

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

class AgentSetDynamicModelOutOfRange(BaseError):
    ...

#########################################################################################################
############################                                          ###################################
#########################################################################################################

class SessionMessage(SystemMessage):
    @classmethod
    def create(cls,content: str,session_id: str,tags:list[str],message_count:int):
        return cls(content=content,id=session_id,additional_kwargs={
            "session_id": session_id,
            'message_count':message_count,
            "memory_type": "session_summary",
            "lc_source":'session_summarization',
            "tags":tags},
            )
    
class SummarizationMiddleware(BaseSummarizationMiddleware):
    @staticmethod
    def _partition_messages(
        conversation_messages: list[AnyMessage],cutoff_index: int,) -> tuple[list[AnyMessage], list[AnyMessage]]:
        """Partition messages into those to summarize and those to preserve."""
        messages_to_summarize = []
        cut_off_message_to_keep = []
        for m in conversation_messages[:cutoff_index]:
            if isinstance(m,(ToolMessage,)):
                cut_off_message_to_keep.append(m)
            elif isinstance(m,HumanMessage) and m.additional_kwargs.get('lc_source',None) == 'summarization':
                cut_off_message_to_keep.append(m) 
            else:
                messages_to_summarize.append(m)

        preserved_messages = conversation_messages[cutoff_index:]
        preserved_messages = cut_off_message_to_keep + preserved_messages

        return messages_to_summarize, preserved_messages
    
    @staticmethod
    def _build_new_messages(summary: str,message_count:int) -> list[HumanMessage]:
        return [HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}",
                additional_kwargs={"lc_source": "summarization",
                                    "message_count":message_count},)]
    
    @override
    async def abefore_model(self, state: AgentState[Any], runtime: Runtime[ContextT]) -> dict[str, Any] | None:
        """Process messages before model invocation, potentially triggering summarization.
        Args:
            state: The agent state.
            runtime: The runtime environment.

        Returns:
            An updated state with summarized messages if summarization was performed.
        """
        messages = state["messages"]
        self._ensure_message_ids(messages)

        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None

        cutoff_index = self._determine_cutoff_index(messages)

        if cutoff_index <= 0:
            return None

        messages_to_summarize, preserved_messages = self._partition_messages(messages, cutoff_index)

        summary = await self._acreate_summary(messages_to_summarize)
        new_messages = self._build_new_messages(summary,len(messages_to_summarize))

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *messages[0:FIRST_KEEP_MESSAGE],
                *new_messages,
                *preserved_messages,
            ]
        }

#########################################################################################################
############################                                          ###################################
#########################################################################################################
@dataclass
class NotifyrContext:
    request_id:str
    session_id:str
    channel:str
    user_id:str
    permissions:set[str]
    auth: Literal['guest','subscribed','registered']
    save:bool=True
    user: Optional[dict]  = field(default=None,init=False)
    retry_count = field(default=0,init=False)

    def __post_init__(self):
        ...
        # NOTE the user will coerce into a schema : base64 -> str -> user_model

class SessionState(TypedDict):
    id:str
    created_at: int
    closed_at: int | None
    messages: List[AnyMessage | SessionMessage]
    tool_message:List[ToolMessage]
    summary:str | None
    metadata:dict[str,Any]
    tags:List[str]

class NotifyrAgentState(AgentState):
    preferences:Dict[str,Any]
    permission:List[str]
    guest:Optional[Dict]
    sessions: Dict[str,SessionState]
    complexity: float

@wrap_model_call
async def do_nothing(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
    return await handler(request)

#########################################################################################################
############################                                          ###################################
#########################################################################################################

@dataclass
class ThreadMetrics:
    messages:list[AnyMessage]  = field(init=True,repr=False)
    total_tokens: int = field(default=0,init=False)
    last_user_tokens: int = field(default=0,init=False)
    tool_call_count: int = field(default=0,init=False)
    summarized_count:int = field(default=0,init=False)
    session_count: int = field(default=0,init=False)
    session_message_count: int = field(default=0,init=False)

    def __post_init__(self):
        
        for m in self.messages:
            if isinstance(m,AIMessage):
               self.total_tokens+= m.usage_metadata["total_tokens"]
            elif isinstance(m,ToolMessage):
                self.tool_call_count+=1
            elif isinstance(m,SessionMessage):
                self.session_count +=1
                self.session_message_count += m.additional_kwargs.get('message_count',0)
            elif isinstance(m,HumanMessage) and m.additional_kwargs.get('lc_source',None) == 'summarization':
                self.summarized_count = m.additional_kwargs.get('message_count',0)
        
        for m in reversed(self.messages):
            if isinstance(m,HumanMessage) and m.additional_kwargs.get('lc_source',None) ==None:
                break
        
        self.last_user_tokens = count_tokens_approximately([m])
             
    def compute_complexity(self,retry_count:int,reference_max_tokens:int)->float:

        (   total_tokens_weight,
            last_user_tokens_weight,
            tool_call_weight,
            summarized_weight,
            session_weight,
            retry_weight,
            message_depth_weight,
        ) = COMPLEXITY_WEIGHT
         
        message_count = len(self.messages)
        total_tokens_score = self.normalize(self.total_tokens,reference_max_tokens)

        summarized_score = self.saturating_log(self.summarized_count,100)
        last_user_score = self.normalize(self.last_user_tokens,reference_max_tokens * 0.25)

        tool_score = self.saturating_log(self.tool_call_count,20)
        retry_score = self.saturating_log(retry_count,5)

        session_score = self.saturating_log(self.session_count,10)
        message_depth_score = self.saturating_log(message_count,150)

        complexity = (
            total_tokens_score * total_tokens_weight
            + last_user_score * last_user_tokens_weight
            + tool_score * tool_call_weight
            + summarized_score * summarized_weight
            + session_score * session_weight
            + retry_score * retry_weight
            + message_depth_score * message_depth_weight
        )   

        return self.clamp(complexity)
        
    @classmethod
    def clamp(cls,value: float, minimum: float = 0.0, maximum: float = 1.0):
        return max(minimum, min(value, maximum))

    @classmethod
    def normalize(cls,value: float, reference: float):
        if reference <= 0:
            return 0.0
        return cls.clamp(value / reference)

    @classmethod
    def saturating_log(cls,value: float, reference: float):
        if value <= 0:
            return 0.0

        return cls.clamp(math.log1p(value) / math.log1p(reference))

#########################################################################################################
############################                                          ###################################
#########################################################################################################

def ContextStrictTrimmerFactory(agentModel:AgentModel,llmModel:LLMProfileModel):

    if agentModel.trimmer == None:
        return do_nothing
    
    @wrap_model_call
    async def trimmer(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
        state:NotifyrAgentState = request.state
        messages= state['messages']

        injected_messages = messages[0:FIRST_KEEP_MESSAGE]
        cutoff_index = FIRST_KEEP_MESSAGE
        message_count = len(messages)

        tool_message = []
        total_tokens = 0
        count = 0

        for i,m in enumerate(messages[FIRST_KEEP_MESSAGE:],start=FIRST_KEEP_MESSAGE):
            if isinstance(m,ToolMessage):
                tool_message.append(m)
                continue
            count+=1
            if isinstance(m,AIMessage):
                total_tokens += m.usage_metadata["total_tokens"]

            if (message_count - FIRST_KEEP_MESSAGE - count) >= agentModel.trimmer.keep_message:
                cutoff_index = i - 2
                break

            if total_tokens >= agentModel.trimmer.tokens_trigger:
                cutoff_index = i # TODO ratio based on the count and the total_token
                break
        
        injected_messages += [state["messages"[cutoff_index:]]]
        request.override(message=injected_messages)

        return await handler(message=injected_messages)

    return trimmer

def SessionInjectionFactory(agentModel:AgentModel,llmModel:LLMProfileModel):
    # TODO filter by session tags

    @wrap_model_call
    async def inject_session_summaries(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
        state:NotifyrAgentState = request.state
        injected_messages = [state["messages"][0:FIRST_KEEP_MESSAGE]]

        for i,(session_id,session) in enumerate(state.get("sessions",{}).items()):
            injected_messages.append(SessionMessage.create(session['summary'],session_id))
            injected_messages.extend(session.get('tool_message',[]))

        injected_messages.extend(state["messages"][FIRST_KEEP_MESSAGE:])
        request.override(messages=injected_messages)
        return await handler(request)

    return inject_session_summaries

#########################################################################################################
############################                                          ###################################
#########################################################################################################

@dynamic_prompt
def dynamic_system_prompt(request: ModelRequest[NotifyrContext]) -> str:
    # if the user is a guest indicate the agent to not hesitate to learn about the user through the conversation tool, 
    # if there's missing keys and it is guest ask them with the conversation tool
    return ''

#########################################################################################################
############################                                          ###################################
#########################################################################################################

def ChatModelFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper,index:int=None)->BaseChatModel:
        api_key =lambda: credentials.to_plain()

        max_output_tokens, max_inputs_token = extract_max_tokens(agentModel, llmModel)

        provider = llmModel.provider

        profile = agentModel.profile.model_dump(exclude=('max_inputs_token',))
        profile = {**BASE_MODEL_PROFILE, **profile,'max_inputs_token':max_inputs_token}

        if isinstance(agentModel.model,str):
            model = agentModel.model
        elif isinstance(agentModel.model,list):
            if not isinstance(index,int):
                raise IndexError(f'Cannot refer the model since the index is not valid: {index}')
            model = agentModel.model[index]
        else:
            raise ValueError(f'Agent model name is not valid: {agentModel.model}')
            
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
                    max_completion_tokens=max_output_tokens,
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
                    max_tokens=max_output_tokens,
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

    # Tuple[ranking,index@models]

    models:list[tuple[int,int]] = [ (MODEL_RANKINGS[llmModel.provider][m],i)  for i,m in enumerate(agentModel.model,) ]
    models = sorted(models,lambda t:t[0])
    chatModels:list[BaseChatModel] = []

    basic_chat_model = None
    summary_model = None

    for (_,index) in models:
        _chat = ChatModelFactory(agentModel,llmModel,credentials,index)
        chatModels.append(_chat)

        if agentModel.dynamicModel.baseChatIndex == index and basic_chat_model == None:
            basic_chat_model = _chat
        
        if agentModel.dynamicModel.summaryChatIndex == index and summary_model == None:
           summary_model = _chat
        
    if basic_chat_model == None:
        basic_chat_model = chatModels[len(models)//2]

    if summary_model == None:
        summary_model = chatModels[0]

    if agentModel.trimmer !=None:
        if agentModel.trimmer.mode == 'summarize':
            middleware  = SummarizationMiddleware(summary_model,
                                          trigger=('tokens',agentModel.trimmer.tokens_trigger),
                                          keep=('messages',agentModel.trimmer.keep_message),
                                          trim_tokens_to_summarize=agentModel.trimmer.tokens_trigger *.75 )
        else:
            middleware = ContextStrictTrimmerFactory(agentModel,llmModel)
    else:
        middleware = do_nothing

    max_tokens = extract_max_tokens(agentModel,llmModel)

    @wrap_model_call
    async def dynamic_model_selection(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
        messages = request.state['messages']
        state:NotifyrAgentState = request.state

        message_count = len(messages)

        if agentModel.dynamicModel.trigger_message == None or message_count < agentModel.dynamicModel.trigger_message:
            return await handler(request)
    
        metrics = ThreadMetrics(messages)
        retry_count = request.runtime.context.retry_count
        if retry_count >=5:
            return handler(request.override(model=chatModels[-1]))

        complexity = metrics.compute_complexity(retry_count,max_tokens.input or MIN_OF_MAX_INPUT_TOKEN)
        if state.get('complexity') != None:
            complexity = 0.75*state['complexity'] + complexity *.25

        state['complexity'] = complexity
        
        index = round((len(chatModels)-1) * state['complexity'])
        index *=agentModel.dynamicModel._reverse
    
        return await handler(request.override(model=chatModels[index]))
    

    return middleware,dynamic_model_selection,basic_chat_model

