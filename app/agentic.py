from app.utils.tools import RunInThreadPool
from app.container import Get


from app.callback import Callbacks_Stream,Callbacks_Sub
from app.services import RedisService
from app.services import VaultService
from app.services import AgentService

from app.depends.dependencies import get_bearer_token
from fastapi import FastAPI,Depends
from app.routers import Routers


def bootstrap_agent_app():
    redisService = Get(RedisService)
    vaultService = Get(VaultService)
    agentService = Get(AgentService)

    def auth_middleware(token: str = Depends(get_bearer_token)):
        agentService.verify_auth(token)

    async def on_startup():
        redisService.register_consumer(callbacks_stream=Callbacks_Stream,callbacks_sub=Callbacks_Sub)
        

    async def on_shutdown():
        redisService:RedisService = Get(RedisService)
        redisService.to_shutdown = True
        await redisService.close_connections()
        await RunInThreadPool(redisService.revoke_lease)()
        await RunInThreadPool(vaultService.revoke_auth_token)()


    app = FastAPI(on_shutdown=[on_shutdown],on_startup=[on_startup],dependencies=[Depends(auth_middleware)])

    for r in Routers:
        app.include_router(r)
    
    return app
