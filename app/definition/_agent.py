import asyncio
from dataclasses import dataclass, field
import math
from typing import Callable, Dict, List, Literal, NamedTuple, Optional, Type, TypedDict,Any, override
from langchain.agents.middleware.types import AgentState, ContextT, dynamic_prompt
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_groq import ChatGroq
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from app.classes.conversation import Auth, Channel
from app.classes.secrets import ChaCha20Poly1305SecretsWrapper
from app.definition._error import BaseError
from app.definition._service import ServiceStatus
from app.models.odm.agents_model import AgentModel,MIN_OF_MAX_INPUT_TOKEN
from app.models.odm.llm_model import LLMProfileModel
from app.prompt.agents_prompt import PERSONALIZED_PROMPT
from app.utils.helper import _make_delay_fn, subset_model
from langgraph.runtime import ExecutionInfo
from langchain.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage,SystemMessage
from langchain.messages import ToolMessage
from langchain_core.messages.utils import count_tokens_approximately
from pydantic import BaseModel, SecretStr, ValidationError
from langchain.agents.middleware import ModelFallbackMiddleware, Runtime, after_agent, before_agent, before_model, wrap_model_call, ModelRequest, ModelResponse,ContextEditingMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
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

class PurposedModel(NamedTuple):
    basic:BaseChatModel
    summary:BaseChatModel
    interrupt:BaseChatModel

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

class AgentMessageLimitExceededError(BaseError):

    def __init__(self, thread_id:str,checkpoint_ns:str,session_id:str,agent:str,limit:str,auth:str):
        super().__init__(thread_id,session_id,agent,limit)
        self.thread_id = thread_id
        self.session_id = session_id
        self.checkpoint_ns = checkpoint_ns
        self.agent = agent 
        self.limit = limit
        self.auth = auth

class AgentSessionAlreadyEndedError(BaseError):
    def __init__(self,session_id:str,execution_info:ExecutionInfo):
        super().__init__()
        self.run_id = execution_info.run_id
        self.session_id = session_id
        self.thread_id = execution_info.thread_id
        self.checkpoint_ns = execution_info.checkpoint_ns

#########################################################################################################
############################                                          ###################################
#########################################################################################################

@dataclass
class NotifyrContext:
    request_id:str
    session_id:str
    channel:Channel
    user_id:str
    auth: Auth
    save:bool=True
    user: Optional[dict]  = field(default=None,init=False)
    retry_count = field(default=0,init=False)

    def __post_init__(self):
        ...
        # NOTE the user will coerce into a schema : base64 -> str -> user_model

ToolClass = Literal['retrieval','execution','discovery','manager','agent']

class BaseToolArtifact(TypedDict):
    process_time:int
    error:Optional[dict]
    hashes:list[str]

class ToolMetadata(TypedDict):
    toolClass:ToolClass
    subclass:str

class SessionState(TypedDict):
    id:str
    created_at: int
    closed_at: int | None
    messages: List[AnyMessage]
    count: int # Count of AIMessage | HumanMessage
    summary:str | None
    total_token:int
    summary_token:int
    metadata:dict[str,Any]
    tags:List[str]

class NotifyrAgentState(AgentState):
    memory:Dict[str,Any]
    policy:Dict[str,Any]
    guest:Optional[Dict]
    sessions: Dict[str,SessionState]
    complexity: float

@wrap_model_call
async def do_nothing(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
    return await handler(request)

#########################################################################################################
############################                                          ###################################
#########################################################################################################

class SessionMessage(SystemMessage):

    @classmethod
    def create(cls,content: str,session_id: str,tags:list[str],message_count:int,token:int):
        return cls(content=content,id=session_id,additional_kwargs={
            "session_id": session_id,
            'message_count':message_count,
            "memory_type": "session_summary",
            'token':token,
            "lc_source":'session_summarization',
            "tags":tags},
            )
    
class SummarizationMiddleware(BaseSummarizationMiddleware):
    """Summarize the tool but keep the raw ToolMessage and maybe keep the tool call"""
    _tool_class_to_keep_as_is_:set[ToolClass] = {'execution','manager'}

    @classmethod
    def _mark_messages(cls,
        conversation_messages: list[AnyMessage],cutoff_index: int,) -> tuple[list[AnyMessage], list[AnyMessage]]:
        """Mark messages as __deleted__ to be filtered out in later middleware"""
        messages_to_summarize = []
        tool_message_count = 0
        for m in conversation_messages[:cutoff_index]:

            if m.additional_kwargs.get('__deleted__',False):
                continue

            if isinstance(m,(ToolMessage,)):
                metadata:ToolMetadata = m.additional_kwargs.get('__tool_metadata__',{})
                if metadata.get('tool_class',None) in cls._tool_class_to_keep_as_is_:
                    continue
                tool_message_count +=1

            elif isinstance(m,HumanMessage) and m.additional_kwargs.get('lc_source',None) == 'summarization':
                continue
            
            m.additional_kwargs['__deleted__'] = True
            messages_to_summarize.append(m)

        return messages_to_summarize,tool_message_count
    
    @staticmethod
    def _build_new_messages(summary: str,message_count:int,tool_message_count:int) -> list[HumanMessage]:
        return [HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}",
                additional_kwargs={"lc_source": "summarization",
                                    "message_count":message_count,
                                    "tool_message_count":tool_message_count,
                                    },)]
    
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

        if cutoff_index <= FIRST_KEEP_MESSAGE:
            return None

        messages_to_summarize,tool_message_count = self._mark_messages(messages, cutoff_index)

        summary = await self._acreate_summary(messages_to_summarize)
        new_messages = self._build_new_messages(summary,len(messages_to_summarize),tool_message_count)

        return {'messages':[
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *messages[:cutoff_index],
                *new_messages,
                *messages[cutoff_index:],
            ]}

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
                if m.usage_metadata:
                    self.total_tokens+= m.usage_metadata.get("total_tokens",0)
            elif isinstance(m,ToolMessage):
                self.tool_call_count+=1
                metadata:ToolMetadata = m.additional_kwargs.get('__tool_metadata__',{})
            elif isinstance(m,SessionMessage):
                self.session_count +=1
                self.session_message_count += m.additional_kwargs.get('message_count',0)
                self.total_tokens += m.additional_kwargs.get('total_token',0)
            elif isinstance(m,HumanMessage) and m.additional_kwargs.get('lc_source',None) == 'summarization':
                self.summarized_count += m.additional_kwargs.get('message_count',0)
                self.total_tokens += m.additional_kwargs.get('total_token',0)
        
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
                chat=  ChatAnthropic(
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
                chat = ChatCohere(
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
                chat = ChatOpenAI(
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
                chat = ChatGroq(
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
    
        return PurposedModel(chat,chat,chat)

def DynamicChatModelFactory(agentModel:AgentModel,llmModel:LLMProfileModel,credentials: ChaCha20Poly1305SecretsWrapper):

    dynamic_middlewares = []

    # Tuple[ranking,index@models]
    models:list[tuple[int,int]] = [ (MODEL_RANKINGS[llmModel.provider][m],i)  for i,m in enumerate(agentModel.model,) ]
    models = sorted(models,lambda t:t[0])
    chatModels:list[BaseChatModel] = []

    basic_chat_model = None
    summary_model = None
    interrupt_model = None

    for i,(_,index) in enumerate(models):
        _chat = ChatModelFactory(agentModel,llmModel,credentials,index)
        chatModels.append(_chat)

        if agentModel.dynamicModel.baseChatIndex == index and basic_chat_model == None:
            chatIndex = i
            basic_chat_model = _chat
        
        if agentModel.dynamicModel.summaryChatIndex == index and summary_model == None:
           summary_model = _chat
        
        if agentModel.dynamicModel.interruptChatIndex == index and interrupt_model == None:
            interrupt_model = _chat
        
    if basic_chat_model == None:
        chatIndex = len(models)//2
        basic_chat_model = chatModels[chatIndex]

    if summary_model == None:
        summary_model = chatModels[0]
    
    if interrupt_model == None:
        interrupt_model = chatModels[0]

    max_tokens = extract_max_tokens(agentModel,llmModel)

    if agentModel.dynamicModel.mode == 'fallback' or agentModel.dynamicModel.mode == 'both':
        if agentModel.dynamicModel._reverse == 1:
            fallback_models = reversed(models[:chatIndex])
        else:
            fallback_models = models[chatIndex:]

        fallback_middleware = ModelFallbackMiddleware(*fallback_models)
        dynamic_middlewares.append(fallback_middleware)
    
    if agentModel.dynamicModel.mode == 'optimization' or agentModel.dynamicModel.mode == 'both':
        @wrap_model_call
        async def dynamic_model_selection(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
            messages = request.messages
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
            index *= agentModel.dynamicModel._reverse
        
            return await handler(request.override(model=chatModels[index]))
        
        dynamic_middlewares.append(dynamic_model_selection)

    return PurposedModel(basic_chat_model,summary_model,interrupt_model),dynamic_middlewares

#########################################################################################################
############################                                          ###################################
#########################################################################################################

def MessageTrimmerFactory(agentModel:AgentModel,llmModel:LLMProfileModel,summary_model:BaseChatModel=None):
    _tool_class_to_keep_as_is_:set[ToolClass] = {'execution','manager'}


    if agentModel.trimmer == None:
        return do_nothing
    
    if agentModel.trimmer == 'trim':

        @wrap_model_call
        async def trimmer(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
            state:NotifyrAgentState = request.state
            messages = state['messages']

            injected_messages = messages[0:FIRST_KEEP_MESSAGE]
            cutoff_index = FIRST_KEEP_MESSAGE
            message_count = len(messages)

            tool_message = []
            tools_to_keep = {}

            total_tokens = 0
            count = 0

            for i,m in enumerate(messages[FIRST_KEEP_MESSAGE:],start=FIRST_KEEP_MESSAGE):
                if m.additional_kwargs.get('__deleted__',False):
                    continue 

                if isinstance(m,ToolMessage):
                    metadata:ToolMetadata = m.additional_kwargs.get('__tool_metadata__',{})
                    if metadata.get('tool_class') in _tool_class_to_keep_as_is_:
                        tool_message.append((i,m))
                    elif agentModel.trimmer.keep_referenced_tools:
                        tools_to_keep[m.tool_call_id] = (i,m)
                    
                count+=1
                if isinstance(m,AIMessage):
                    if m.usage_metadata:
                        total_tokens += m.usage_metadata.get("total_tokens",0)

                if (message_count - FIRST_KEEP_MESSAGE - count) >= agentModel.trimmer.keep_message:
                    cutoff_index = i - 2
                    break

                if total_tokens >= agentModel.trimmer.tokens_trigger:
                    cutoff_index = i # TODO ratio based on the count and the total_token
                    break
            
            if agentModel.trimmer.keep_referenced_tools:
                for i,m in enumerate(messages[cutoff_index:],start=cutoff_index):
                    if not isinstance(m,AIMessage):
                        continue
                    for t in m.tool_calls:
                        if t in tools_to_keep:
                            tool_message.append(tools_to_keep[t['id']])
                
            if agentModel.trimmer.keep_referenced_tools:
                tool_message = sorted(tool_message,key=lambda v:v[0])

            injected_messages += [ t[1] for t in  tool_message ] 
            injected_messages += state["messages"][cutoff_index:]
            
            request = request.override(messages=injected_messages)
            return await handler(request)
            
        return trimmer
    
    if summary_model == None:
        ...
    
    return SummarizationMiddleware(summary_model,
        trigger=('tokens',agentModel.trimmer.tokens_trigger),
        keep=('messages',agentModel.trimmer.keep_message),
        trim_tokens_to_summarize=agentModel.trimmer.tokens_trigger *.75
        )

def SessionInjectionFactory(agentModel:AgentModel,llmModel:LLMProfileModel):
    # TODO filter by session tags

    @wrap_model_call
    async def inject_session_summaries(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
        injected_messages = []
        state:NotifyrAgentState = request.state
        for i,(session_id,session) in enumerate(state.get("sessions",{}).items()):
            message = SessionMessage.create(session['summary'],session_id,session.get('tags',[],
                                            len(session.get('messages',[])),session.get('total_token',0)))
            injected_messages.append(message)

        injected_messages.extend(request.messages)
        request = request.override(messages=injected_messages)
        return await handler(request)

    return inject_session_summaries

def SemanticInterruptParserFactory(agentModel:AgentModel,model:BaseChatModel,agentService:Any):
    
    model = model.with_structured_output(include_raw=True)
    model = model.with_retry((ValidationError,),stop_after_attempt=2)

    @before_agent(can_jump_to=['end','tools','model'])
    async def interrupt_middleware(state: NotifyrAgentState, runtime: Runtime[NotifyrContext]):
        if runtime.context.channel not in agentModel.interruptChannel:
            return None

        graph:CompiledStateGraph[NotifyrAgentState,NotifyrContext,Any,Any] = None
        if (graph:=getattr(agentService,'agent',None)) == None:
            return None
        
        config = {"configurable":{"thread_id":runtime.execution_info.thread_id,
                                "checkpoint_ns":runtime.execution_info.checkpoint_ns}}

        snapshot = await graph.aget_state(config)
        if not snapshot.interrupts:
            return None

        last_message =  []
        last_message.append(state['messages'][-1])

        for m in reversed(state['messages']):
            if isinstance(m,AIMessage):
                last_message.append(m)
                break
        
        message = await model.ainvoke(last_message)
        ...

        return None
  
    return interrupt_middleware

def MessageLimitFactory(agentModel:AgentModel):

    config = agentModel.messageLimit.model_dump()

    @before_model(can_jump_to=['end'])
    async def message_limiter(state: NotifyrAgentState, runtime: Runtime[NotifyrContext]) -> dict[str, Any] | None:
        count = 0
        limit = config.get(runtime.context.auth,None)
        
        if limit == None:
            return None
        
        for val in [*state['sessions'].values(),*state['messages']]:
            if isinstance(val,dict):
                count+=val['count']
            elif isinstance(val,(AIMessage,HumanMessage)):
                count+=1
            else:
                continue

            if count == limit -1 :
                ai_message = AIMessage('Message limit is reached with the agent',additional_kwargs={'__ended__':True})
                return {'messages':[ai_message],'jump_to':'end'}
            
            if count >= limit:
                raise AgentMessageLimitExceededError(runtime.execution_info.thread_id,
                                               runtime.execution_info.checkpoint_ns,
                                               runtime.context.session_id,
                                               agentModel.id,
                                               limit,
                                               runtime.context.auth,
                                               )
        return None

    return message_limiter

def ThrottleFactory():

    auth_wait_fn:dict[Auth,Callable[[],int]] = {}
    channel_wait_fn:dict[Channel,Callable[[],int]] = {}

    auth_wait_fn["guest"] = _make_delay_fn(normal=(2000, 500))
    auth_wait_fn["subscribed"] = _make_delay_fn(normal=(1000, 300))
    auth_wait_fn["registered"] = _make_delay_fn(normal=(500, 200))

    channel_wait_fn['call'] = _make_delay_fn(normal=(200, 50))
    channel_wait_fn['live-chat'] = _make_delay_fn(normal=(400, 100))
    channel_wait_fn['message'] = _make_delay_fn(normal=(800, 200))
    channel_wait_fn['sms'] = _make_delay_fn(normal=(1200, 300))
    channel_wait_fn['email'] = _make_delay_fn(normal=(1500, 400))


    @wrap_model_call
    async def throttle(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
        
        auth_delay = auth_wait_fn.get(request.runtime.context.auth,1)()
        channel_delay = auth_wait_fn.get(request.runtime.context.channel,1)()

        await asyncio.sleep(channel_delay/1000)
        await asyncio.sleep(auth_delay/1000)
        return await handler(request)
    
    return throttle

#########################################################################################################
############################                                          ###################################
#########################################################################################################

to_filter_tool_class:set[ToolClass] = {'manager'}

@wrap_model_call
async def filter_non_relevant_message(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
    messages = []
    seen = set()
    
    for m in request.messages:

        if m.additional_kwargs.get('__deleted__',False):
            continue

        if isinstance(m,ToolMessage):
            metadata:ToolMetadata = m.additional_kwargs.get('__tool_metadata__',{})

            if metadata.get('tool_class', None) in to_filter_tool_class:
                continue

            artifact:Optional[BaseToolArtifact] = m.artifact
            if artifact:
                hashes = set(artifact.get("hashes",[]))
                if hashes and (len(hashes.intersection(seen)) == len(hashes)):
                    continue
                    
                seen.update(hashes)
            
        messages.append(m)
        
    request.override(messages = messages)
    return await handler(request)

@after_agent
async def inject_ai_turn(state: NotifyrAgentState, runtime: Runtime[NotifyrContext]) -> dict[str, Any] | None:
    ai_turn = state['messages'][-1]
    ai_turn.additional_kwargs['__turn__'] = True
    return None

def DynamicSystemPromptFactory(memoryModel:Type[BaseModel],memory_enabled):
    MemoryModel =subset_model(memoryModel,f'Update{memoryModel.__class__.__name__}',optional=True)

    @dynamic_prompt
    def dynamic_system_prompt(request: ModelRequest[NotifyrContext]) -> SystemMessage:
        state:NotifyrAgentState = request.state
        system = request.system_message
        content:list = system.content.copy()
        auth =  request.runtime.context.auth
        personalized_prompt = PERSONALIZED_PROMPT(
            request.runtime.context.channel,
            auth,
            request.runtime.context.user if auth != 'guest' else state.get('guest',{}),
            MemoryModel(**state.get('memory',{}) if memory_enabled else None),
        )
        prompt = {'type':'text','text':personalized_prompt}
        content.append(prompt)
        return SystemMessage(content)
    
    return dynamic_system_prompt
    
@before_model
async def guard_session_ends(state: NotifyrAgentState, runtime: Runtime[NotifyrContext]):
    for m in reversed(state['messages']):
        if isinstance(m,AIMessage):
            break
            
    if m.additional_kwargs.get('__ended__',None):
        raise AgentSessionAlreadyEndedError(runtime.context.session_id,runtime.execution_info)
    
    return None
    
@wrap_model_call
async def handle_agent(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse])->ModelResponse:
    return await handler(request)
    