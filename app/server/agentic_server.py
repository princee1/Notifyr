import asyncio

from fastapi.responses import StreamingResponse
from app.classes.prompt import PromptToken
from app.utils.constant import CostConstant
from app.utils.tools import RunInThreadPool
from app.container import Get,Register
from app.callback import Callbacks_Stream,Callbacks_Sub
from app.services import RedisService
from app.services import VaultService
from app.services import AgentService
from app.services import MongooseService
from app.services import QdrantService
from app.services import CostService
from app.services import ReactiveService
from app.depends.dependencies import get_bearer_token
from fastapi import FastAPI,Depends, HTTPException, Request
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

async def on_purchase_token_next(tokens:PromptToken):
    costService = Get(CostService)
    cost = TokenCost(tokens['request_id'],tokens['issuer'])
    cost.purchase('input token',1,tokens['input'])
    cost.purchase('output token',1,tokens['output'])
    bill = cost.generate_bill()
    await costService.deduct_credits(CostConstant.TOKEN_CREDIT,bill)

def on_purchase_token_complete():
    ...

def bootstrap_agent_app()->FastAPI:
    redisService = Get(RedisService)
    vaultService = Get(VaultService)
    agentService = Get(AgentService)
    mongooseService = Get(MongooseService)
    qdrantService = Get(QdrantService)
    reactiveService = Get(ReactiveService)

    grpcTask = GrpcTask()    

    def auth_depends(token: str = Depends(get_bearer_token)):
        if agentService.auth_header != token:
            raise HTTPException(status_code=401,detail="Unauthorized")

    async def on_startup():
        mongooseService.start()
        redisService.register_consumer(callbacks_stream=Callbacks_Stream,callbacks_sub=Callbacks_Sub)
        grpcTask.set_task(asyncio.create_task(agentService.serve()))
        agentService.subscribe_token(
            on_next=lambda t: asyncio.create_task(on_purchase_token_next(t)),
            on_complete=on_purchase_token_complete
            )

    async def on_shutdown():
        mongooseService.shutdown()

        redisService.to_shutdown = True
        await redisService.close_connections()
        await RunInThreadPool(redisService.revoke_lease)()
        await RunInThreadPool(mongooseService.revoke_lease)()

        await RunInThreadPool(vaultService.revoke_auth_token)()
        await agentService.stop_grpc()
        grpcTask.cancel_task()

        agentService.complete_purchase()

    app = FastAPI(on_shutdown=[on_shutdown],
                  on_startup=[on_startup],
                  dependencies=[Depends(auth_depends)]
                  )
    
    @app.get('/health/',dependencies=[Depends(auth_depends)],)
    async def health(response:StreamingResponse,request:Request):
        
        async def health_stream():
            while True:
                if await request.is_disconnected():
                    break
                yield 'pong'
                asyncio.sleep(2)
 
        return StreamingResponse(
            content=health_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
                }
        )

    for r in Routers:
        app.include_router(r)
    
    return app
