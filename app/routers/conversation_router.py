from typing import Annotated
from fastapi import APIRouter, Depends
from app.container import Get
from app.definition._router import MINI_SERVICE_HANDLER_DETAILS, SERVICE_HANDLER_DETAILS, HandlerDetails, auth_depends, exception_handler, get_instance_id, lock_service_wrapper,service_yielder
from app.services.agent.agent_service import AgentMiniService, AgentService
from app.services.database.mongoose_service import MongooseService
from app.utils.constant import AgenticConstant
from app.errors.agent_error import AgentNotAvailableError,AgentOnlyAsSubAgentError

prefix=AgenticConstant.CONVERSATION_ROUTER('')
agent_yielder = service_yielder(AgentService)


AGENT_HANDLER_DETAILS = {AgentOnlyAsSubAgentError:HandlerDetails(),
                         AgentNotAvailableError:HandlerDetails()}

def ConversationRouter():

    agentService:AgentService = Get(AgentService)
    mongooseService = Get(MongooseService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown],dependencies=[Depends(auth_depends)])

    @router.get('/chat/{service}')
    @exception_handler(AGENT_HANDLER_DETAILS)
    @exception_handler(SERVICE_HANDLER_DETAILS)
    @exception_handler(MINI_SERVICE_HANDLER_DETAILS)
    @lock_service_wrapper(MongooseService)
    async def fetch_chat(agent:Annotated[AgentMiniService,Depends(agent_yielder)],instance_id:str=Depends(get_instance_id)):
        agent._verify_status(True)

    @router.delete('/chat/{service}')
    @exception_handler(AGENT_HANDLER_DETAILS)
    @exception_handler(SERVICE_HANDLER_DETAILS)
    @exception_handler(MINI_SERVICE_HANDLER_DETAILS)
    @lock_service_wrapper(MongooseService)
    async def delete_chat(agent:Annotated[AgentMiniService,Depends(agent_yielder)],instance_id:str=Depends(get_instance_id)):
        agent._verify_status(True)

    @router.delete('/graph/{service}')
    @exception_handler(AGENT_HANDLER_DETAILS)
    @exception_handler(SERVICE_HANDLER_DETAILS)
    @exception_handler(MINI_SERVICE_HANDLER_DETAILS)
    @lock_service_wrapper(MongooseService)
    async def fetch_graph(agent:Annotated[AgentMiniService,Depends(agent_yielder)],instance_id:str=Depends(get_instance_id)):
        agent._verify_status(True)
    
    @router.delete('/state/{service}')
    @exception_handler(AGENT_HANDLER_DETAILS)
    @exception_handler(SERVICE_HANDLER_DETAILS)
    @exception_handler(MINI_SERVICE_HANDLER_DETAILS)
    @lock_service_wrapper(MongooseService)
    async def fetch_state(agent:Annotated[AgentMiniService,Depends(agent_yielder)],instance_id:str=Depends(get_instance_id)):
        agent._verify_status(True)
        
    @router.get('/interrupts/{service}')
    @exception_handler(AGENT_HANDLER_DETAILS)
    @exception_handler(SERVICE_HANDLER_DETAILS)
    @exception_handler(MINI_SERVICE_HANDLER_DETAILS)
    @lock_service_wrapper(MongooseService)
    async def fetch_interrupts(agent:Annotated[AgentMiniService,Depends(agent_yielder)],instance_id:str=Depends(get_instance_id)):
        agent._verify_status(True)
    
    @router.post('/interrupts/{service}')
    @exception_handler(AGENT_HANDLER_DETAILS)
    @exception_handler(SERVICE_HANDLER_DETAILS)
    @exception_handler(MINI_SERVICE_HANDLER_DETAILS)
    @lock_service_wrapper(MongooseService)
    async def resume_interrupts(agent:Annotated[AgentMiniService,Depends(agent_yielder)],instance_id:str=Depends(get_instance_id)):
        agent._verify_status(True)
    
    
