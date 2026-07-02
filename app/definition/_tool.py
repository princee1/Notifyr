from dataclasses import dataclass, field
from time import time
from pydantic import BaseModel, Field
from app.models.odm.agents_model import AgentModel, StoreMemoryPolicy
from app.models.odm.tools_model import ContextCondition, ToolModel
from langchain.messages import SystemMessage, HumanMessage,ToolMessage
from langchain.agents.middleware import ToolCallLimitMiddleware, ToolRetryMiddleware, wrap_tool_call,ModelRequest, ModelResponse
from typing import Any, Callable, Dict, Literal, Optional, Set, Type, TypedDict
from app.definition._error import BaseError
from app.definition._agent import NotifyrContext,NotifyrAgentState,ToolClass,ToolMetadata,BaseToolArtifact
from langchain.tools import BaseTool, ToolRuntime as BaseToolRuntime
from langchain_core.messages.utils import count_tokens_approximately
from langchain.agents.middleware import  Runtime, before_agent
from app.prompt import rag_prompt
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.base import BaseStore


#########################################################################################################
############################                                          ###################################
#########################################################################################################
class ToolError(BaseError):
    subclass:str ='Tool'

    def __init__(self, prompt_context:str,artifact:dict,metadata:dict,tool_call_id:str):
        super().__init__()
        self.prompt_context = prompt_context
        self.artifact = artifact
        self.tool_call_id = tool_call_id

        self.metadata = {'__error_metadata__':{'subclass':self.subclass}}
        if isinstance(metadata,dict):
            self.metadata.update(metadata)

class RetryToolError(ToolError):
    subclass:str ='Retry'

class SkipToolError(ToolError):
    subclass:str ='Skip'

    def __init__(self, artifact,metadata,tool_call_id):
        super().__init__('',artifact,metadata,tool_call_id)
    
class UnexpectedToolError(ToolError):
    subclass:str ='Unexpected Error'
    
#########################################################################################################
############################                                          ###################################
#########################################################################################################

ToolStatus = Literal['success','error']

ToolRuntime=BaseToolRuntime[NotifyrContext,NotifyrAgentState]

class ToolContextFactory:

    def __init__(self,marked:int = 5,deleted:bool = None,artifact:dict=None,option:dict=None):
        """
        deleted: None: dont add the __deleted__
                 False: only when theres an error
                 True: immediately
        """
        self.start_time = 0
        self.end_time = 0
        self.marked = marked
        self.deleted = deleted
        self.status:ToolStatus = 'error' 
        self.deleted_status = None
        self.error = None

        self.artifact = artifact or {}
        self.option = option or {}

    @property
    def delta(self):
        return self.end_time - self.start_time
    
    def as_artifact(self,other:dict|None=None):
        artifact:BaseToolArtifact = {'process_time':self.delta}

        artifact.update(self.artifact)
        
        if self.error != None:
            artifact['error'] = self.error
        
        return artifact
 
    def as_option(self):
        option = {'__marked__':self.marked,}

        option.update(self.option)

        if self.deleted == None:
            return option
        
        if self.deleted:
            option['__deleted__'] = True
        
        if self.status == 'error':
            option['__deleted__'] = True
        
        return option

    def update(self,data:dict|None,what:Literal['artifact','option','error']='artifact'):
        if not data:
            return

        if what == 'artifact':
            self.artifact.update(data)
        elif what == 'option':
            self.option.update(data)
        elif what == 'error':
            if self.error == None:
                self.error = {}

            self.error.update(data)
        else:
            ...

    def recreate_error(self,e:BaseError):
        ...

    async def __aenter__(self):
        self.start_time = time()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        self.end_time = time()

        if exc_type is None:
            self.marked = 1
            self.status = 'success'
            return True

        if isinstance(exc,BaseError):
            self.error = {}
        
        return False

#########################################################################################################
############################                TOOL DEFINITION           ###################################
#########################################################################################################

class Tool:

    Condition: ContextCondition = None

    def __init__(self,config:ToolModel,storePolicy:StoreMemoryPolicy,storeSchema:Type[BaseModel]|None):
        self.config = config
        self.storeSchema = storeSchema
        self.storePolicy = storePolicy

        self.metadata = self.to_metadata()
    
    @property
    def name(self):
        return self.config.alias

    @property
    def description(self):
        return self.config.description

    @property
    def arg_schema(self)->Type[BaseModel]:
        ...
    
    @property
    def tool_id(self):
        return self.config.id

    @classmethod
    def to_metadata(cls,tool:ToolClass,subclass:str)->Dict[Literal['__tool_metadata__'],ToolMetadata]:
        return {'__tool_metadata__':ToolMetadata(toolClass=tool,subclass=subclass)}
        
    def to_condition(self):
        return [self.Condition,self.config.condition]

    def to_limit(self)->None | ToolCallLimitMiddleware:
        if self.config.callGuard == None:
            return None
        
        if self.config.callGuard._limit:
            return None
        
        return ToolCallLimitMiddleware(tool_name=self.name,
                                       thread_limit=self.config.callGuard.thread_limit,
                                       run_limit=self.config.callGuard.run_limit,
                                       )

    def to_hitl(self):
        if self.config.interrupt_on == None:
            return None
        if isinstance(self.config.interrupt_on,bool):
            return {self.name:self.config.interrupt_on} 
        return {self.name:self.config.interrupt_on.model_dump()}

    def to_retry(self)->None | ToolRetryMiddleware:
        if self.config.callGuard == None:
            return None

        if self.config.callGuard._retry:
            return None
        
        return  ToolRetryMiddleware(
            on_failure='error',
            retry_on=(RetryToolError,),
            tools=[self.name],
            max_delay=self.config.callGuard.max_delay,
            max_retries=self.config.callGuard.max_retries
        )

    
    def to_artifact(self,context:Any)->BaseToolArtifact:
        ...
    
    async def read_store(self,namespace:tuple[str,...],key:str,_store_:BaseStore=None):
        ...
    
    async def write_store(self,namespace:tuple[str,...],key:str,_store_:BaseStore=None):
        ...

    async def __call__(self,runtime:ToolRuntime):
        ...
    
    @classmethod
    def compute_token(cls,content:str):
        return count_tokens_approximately([ToolMessage(content)])
    
class ExecutionTool(Tool):
    
    @classmethod
    def to_metadata(cls,subclass:str):
        return super().to_metadata('execution', subclass)

class RetrievalTool(Tool):
    
    @classmethod
    def to_metadata(cls,subclass:str):
        return super().to_metadata('retrieval', subclass)

class ManagerTool(Tool):

    @classmethod
    def to_metadata(cls,subclass:str):
        return super().to_metadata('manager', subclass)

class DiscoveryTool(Tool):
    
    @classmethod
    def to_metadata(cls,subclass:str):
        return super().to_metadata('discovery', subclass)


#########################################################################################################
############################        TOOL MIDDLEWARE                   ###################################
#########################################################################################################

@wrap_tool_call
async def handle_tool_errors(request:ModelRequest[NotifyrContext],handler:Callable[[ModelRequest[NotifyrContext]], ModelResponse]):
    try:
        try:
            return await handler(request)
        except RetryToolError as e:
            add_kwargs = {'__marked__':2}
            raise e
        except SkipToolError as e:
            add_kwargs = {'__deleted__':True}
            raise e
        except UnexpectedToolError as e:
            add_kwargs = {'__marked__':8}
            raise e
    except ToolError as e:
        return ToolMessage(
            e.prompt_context,
            artifact = e.artifact,
            status='error',
            tool_call_id = e.tool_call_id,
            additional_kwargs = {**add_kwargs,**e.metadata}
        )
        

@wrap_tool_call
async def dynamic_tool_selection(request: ModelRequest[NotifyrContext],handler: Callable[[ModelRequest[NotifyrContext]], ModelResponse]) -> ModelResponse:

    context = request.runtime.context
    filtered_tools = []
    for t in request.tools:
        condition:ContextCondition

        for condition in t.extras.get('__condition__',[]):
            if condition == None:
                filtered_tools.append(t)

            if condition.as_is == None:
                filtered_tools.append(t)
            
            if condition.verify(context.auth,context.channel,context.user):
                filtered_tools.append(t)
        
    request = request.override(tools=filtered_tools)
    return await handler(request)

#########################################################################################################
############################            RAG Factory                   ###################################
#########################################################################################################

def TwoStepRagFactory(tools:list[RetrievalTool]):

    @before_agent
    async def vector_retriever(state: NotifyrAgentState, runtime: Runtime[NotifyrContext]):
        message:HumanMessage = state['messages'][-1]
        for i,c in enumerate(message.content):
            if c['type'] == 'text':
                query = c['text']
                break

        context = ''
        for tool in tools:
            context:ToolMessage = await tool(query,runtime)
            context +=context.text

        context = rag_prompt.AUGMENTED_QUERY_TEMPLATE(context,query)
        message.content[i] = {'type':'text','text':context}
        return None

    return vector_retriever

def HybridRAGFactory(agentModel:AgentModel,model:BaseChatModel,tools:list[BaseTool]):
    """Example directly taken from https://docs.langchain.com/oss/python/langgraph/agentic-rag#6-generate-an-answer"""
    
    class GradeDocuments(BaseModel):
        """Grade documents using a binary score for relevance check."""

        binary_score:Literal['yes','no'] = Field(description="Relevance score: 'yes' if relevant, or 'no' if not relevant")

    grader_model =  model.model_copy(update={'temperature':True}).with_structured_output(GradeDocuments)
    retriever_model = model.model_copy(update={'temperature':True}).bind_tools(tools)

    async def generate_query_or_respond(state: NotifyrAgentState):
        """Call the model to generate a response based on the current state. Given
        the question, it will decide to retrieve using the retriever tool, or simply respond to the user.
        """
        response = await retriever_model.ainvoke(state["messages"])
        return {"messages": [response]}
    
    async def grade_documents(state: NotifyrAgentState,) -> Literal["generate_answer", "rewrite_question"]:
        """Determine whether the retrieved documents are relevant to the question."""

        question = state["messages"][0].content
        context = state["messages"][-1].content

        prompt = rag_prompt.GRADE_DOCUMENT_TEMPLATE(context,question)
        response:GradeDocuments = await grader_model.ainvoke([{"role": "user", "content": prompt}])

        return 'generate_answer' if response.binary_score == 'yes' else 'rewrite_question'

    async def rewrite_question(state: NotifyrAgentState):
        """Rewrite the original user question."""
        #question:HumanMessage = next([m for m in reversed(state['messages']) if isinstance(m,HumanMessage)])
        question = state["messages"][0]
        prompt = rag_prompt.REWRITE_TEMPLATE(question.content)
        response = await model.ainvoke([{"role": "user", "content": prompt}])
        return {"messages": [HumanMessage(content=response.content)]}
    
    async def generate_answer(state: NotifyrAgentState):
        """Generate an answer."""
        question = state["messages"][0].content
        context = state["messages"][-1].content
        prompt = rag_prompt.GENERATE_TEMPLATE(context,question)
        response = await model.ainvoke([{"role": "user", "content": prompt}])
        return {"messages": [response]}

    def route_on_tool_calls(state: NotifyrAgentState):
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    workflow = StateGraph(NotifyrAgentState,NotifyrContext)

    workflow.add_node(generate_query_or_respond)
    workflow.add_node("retrieve", ToolNode(tools))
    workflow.add_node(rewrite_question)
    workflow.add_node(generate_answer)

    workflow.add_edge(START, "generate_query_or_respond")
    workflow.add_conditional_edges("generate_query_or_respond",route_on_tool_calls,{"tools": "retrieve",END: END,})

    workflow.add_conditional_edges("retrieve",grade_documents)
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("rewrite_question", "generate_query_or_respond")

    rag_agent = workflow.compile()

    async def hybrid_rag(query:str,runtime:ToolRuntime):
        response = await rag_agent.ainvoke(HumanMessage(query))
        return ToolMessage()
    
    return hybrid_rag
        
