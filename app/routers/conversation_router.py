from fastapi import APIRouter, Depends
from app.container import Get
from app.definition._router import get_instance_id
from app.services.agent.agent_service import AgentService
from app.services.database.mongoose_service import MongooseService
from app.utils.constant import AgenticConstant

prefix=AgenticConstant.CONVERSATION_ROUTER('')

def ConversationRouter():

    agentService = Get(AgentService)
    mongooseService = Get(MongooseService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])

   