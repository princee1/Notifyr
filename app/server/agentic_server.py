import asyncio
from app.services.reactive_service import ReactiveService
from app.utils.tools import RunInThreadPool
from app.container import Get,Register
from app.callback import Callbacks_Stream,Callbacks_Sub
from app.services import RedisService
from app.services import VaultService
from app.services import AgentService
from app.services import MongooseService
from app.services import QdrantService
from app.depends.dependencies import get_bearer_token
from fastapi import FastAPI,Depends
from app.routers import Routers
from app.cost.token_cost import TokenCost


class GrpcTask:
    def __init__(self):
        self.task:asyncio.Task = None
    
    def set_task(self,task:asyncio.Task):
        self.task = task
    
    def cancel_task(self):
        if self.task:
            try:
                self.task.cancel()
            except asyncio.CancelledError as e:
                pass
            except Exception:
                pass
            self.task = None

def bootstrap_agent_app()->FastAPI:
    redisService = Get(RedisService)
    vaultService = Get(VaultService)
    agentService = Get(AgentService)
    mongooseService = Get(MongooseService)
    qdrantService = Get(QdrantService)
    reactiveService = Get(ReactiveService)

    grpcTask = GrpcTask()    

    def auth_depends(token: str = Depends(get_bearer_token)):
        agentService.verify_auth(token)

    async def on_startup():
        mongooseService.start()
        redisService.register_consumer(callbacks_stream=Callbacks_Stream,callbacks_sub=Callbacks_Sub)
        grpcTask.set_task(asyncio.create_task(agentService.serve()))
        
    async def on_shutdown():
        mongooseService.shutdown()

        redisService:RedisService = Get(RedisService)
        redisService.to_shutdown = True
        await redisService.close_connections()
        await RunInThreadPool(redisService.revoke_lease)()
        await RunInThreadPool(mongooseService.revoke_lease)()

        await RunInThreadPool(vaultService.revoke_auth_token)()
        await agentService.stop()
        grpcTask.cancel_task()

    app = FastAPI(on_shutdown=[on_shutdown],
                  on_startup=[on_startup],
                  dependencies=[Depends(auth_depends)]
                  )

    for r in Routers:
        app.include_router(r)
    
    return app
