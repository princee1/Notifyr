from fastapi import APIRouter, Depends
from app.container import Get
from app.services.agent.agent_service import AgentService
from app.services.database.mongoose_service import MongooseService

def AgentRouter():
    prefix:str = ''

    agentService:AgentService = Get(AgentService)
    mongooseService:MongooseService= Get(MongooseService)

    async def on_startup():
        ...
    
    async def on_shutdown():
        ...

    router = APIRouter(prefix=prefix,on_startup=[on_startup],on_shutdown=[on_shutdown])
