import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, WebSocketException,status
from app.classes.prompt import PromptToken
from app.definition._router import auth_depends, get_instance_id
from app.utils.constant import CostConstant, HTTPHeaderConstant
from app.utils.toolbox import RunInThreadPool
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

    async def on_startup():
        mongooseService.start()
        redisService.register_consumer(callbacks_stream=Callbacks_Stream,callbacks_sub=Callbacks_Sub)
        await agentService.serve()
        agentService.subscribe_token(
            on_next=lambda t: asyncio.create_task(on_purchase_token_next(t)),
            on_complete=on_purchase_token_complete
            )

    async def on_shutdown():
        mongooseService.shutdown()

        redisService.to_shutdown = True
        await redisService.close_connections(True)
        await RunInThreadPool(redisService.revoke_lease)()
        await RunInThreadPool(mongooseService.revoke_lease)()

        await RunInThreadPool(vaultService.revoke_auth_token)()
        await agentService.stop_grpc()

        agentService.complete_purchase()

    app = FastAPI(on_shutdown=[on_shutdown],
                  on_startup=[on_startup],
                  )
    
    @app.websocket("/health/")
    async def health(ws:WebSocket):
        if not (instance_id:=ws.headers.get(HTTPHeaderConstant.X_NOTIFYR_APP_INSTANCE_ID,None)):
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION,reason="Missing instance id")
        
        if not (auth:=ws.headers.get('Authorization',None)):
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION,reason="Missing authorization header")

        if auth != f"Bearer {agentService.AgenticAPIKey}":
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION,reason="Unauthorized")

        await ws.accept()

        try:
            while True:
                await ws.send_text("pong")
                await asyncio.sleep(60)

        except WebSocketDisconnect as e:
            print(f"client:{instance_id} disconnected")

        except Exception as e:
            print("websocket error:", e)
    
    @app.post('/ping/',status_code=status.HTTP_200_OK, dependencies=[Depends(auth_depends)])
    async def ping(request:Request,instance_id:str=Depends(get_instance_id)):
        return None

    for r in Routers:
        app.include_router(r)
    
    return app
