import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable
from functools import partial, wraps
from app.definition._service import LinkDep, Service,BaseService
from app.grpc import agent_message
from app.services.agent.remote_agent_service import RemoteAgentService
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.classes.conversation import Message, Reply

def message_to_request(message:Message,content_block_limit:int=3)->agent_message.PromptRequest:
    message.content_block = message.content_block[content_block_limit:]
    return agent_message.PromptRequest(
        message.agent,
        message.prompt,
        message.user,
        message.thread,
        message.model_dump(include={'content_block'}).get('content_block',[]),
        message.mess_id,
        message.send_at
    )

def answer_to_reply(answer:agent_message.PromptAnswer)->Reply:
    return Reply(**answer.export())

def iterator_factory(callback:AsyncGenerator[Any,Message],wait=0.2,limit=3):
    @wraps
    async def request_generator():
        async for message in callback():
            request = message_to_request(message,limit)
            request = request.to_proto()
            yield request
            asyncio.sleep(wait)
    return request_generator()


@Service(links=[LinkDep(RedisService,to_build=True),LinkDep(MongooseService,to_build=True)])
class ChatService(BaseService):
    """Answer message with priority because of the rate limit """

    def __init__(self,configService:ConfigService,mongooseService:MongooseService,remoteAgentService:RemoteAgentService,redisService:RedisService,costService:CostService) -> None:
        super().__init__()
        self.mongooseService = mongooseService
        self.remoteAgentService = remoteAgentService
        self.redisService = redisService
        self.configService = configService
        self.costService = costService
    
    async def start_chat(self):
        ...
    
    async def end_chat(self):
        ...
    
    async def fetch_chat(self,):
        ...
    
    async def stream_answer(self,generator:AsyncGenerator[Any,Message],_agent:str,*args,_wait=0.5,**kwargs):
        generator = partial(generator,*args,**kwargs,wait=_wait)
        generator = iterator_factory(generator,wait=_wait,limit=self.configService.LANGCHAIN_MULTIMODAL_COUNT)
        async with self.remoteAgentService.statusLock.reader:
            async with self.remoteAgentService.MiniServiceStore.lock(_agent) as remoteAgent:
                reply = await remoteAgent.StreamPrompt(generator)
                reply = answer_to_reply(reply)
                return reply

    async def stream_answer_stream(self,generator:AsyncGenerator[Any,Message],_agent:str,*args,_wait=0.5,**kwargs):
        generator = partial(generator,*args,**kwargs)
        generator = iterator_factory(generator,wait=_wait,limit=self.configService.LANGCHAIN_MULTIMODAL_COUNT)
        async with self.remoteAgentService.statusLock.reader:
            async with self.remoteAgentService.MiniServiceStore.lock(_agent) as remoteAgent:
                async for reply in remoteAgent.S2SPrompt(generator):
                    reply = answer_to_reply(reply)
                    yield reply

    async def answer(self,message:Message):
        """Answer message with priority because of the rate limit """
        async with self.remoteAgentService.statusLock.reader:
            async with self.remoteAgentService.MiniServiceStore.lock(message.agent) as remoteAgent:
                request = message_to_request(message,self.configService.LANGCHAIN_MULTIMODAL_COUNT)
                answer = await remoteAgent.Prompt(request)
                reply = answer_to_reply(answer)
                return reply

    async def answer_stream(self,message:Message):
        """Answer message with priority because of the rate limit """
        async with self.remoteAgentService.statusLock.reader:
            async with self.remoteAgentService.MiniServiceStore.lock(message.agent) as remoteAgent:
                request = message_to_request(message,self.configService.LANGCHAIN_MULTIMODAL_COUNT)
                async for answer in remoteAgent.PromptStream(request):
                    reply = answer_to_reply(answer)
                    yield reply
