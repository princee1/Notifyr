
import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable
from functools import partial, wraps
from app.definition._service import LinkDep, Service,BaseService
from app.grpc import agent_message
from app.services.agent.remote_agent_service import RemoteAgentMiniService, RemoteAgentService
from app.services.config_service import ConfigService
from app.services.cost_service import CostService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.classes.conversation import Message, Reply, Session, Thread, User
from app.services.setting_service import SettingService
from app.services.vault_service import VaultService
from app.services.worker.arq_service import ArqIngestTaskService

def message_to_request(message:Message,session:Session,user:User,content_block_limit:int=3)->agent_message.PromptRequest:
    content_block_limit = content_block_limit or 3
    message.content_block = message.content_block[content_block_limit:]
    context = agent_message.Context(
        user.user_id,
        session.request_id,
        session.session_id,
        session.channel,
        user.auth,
        True,
        user.encoded_user,
        session.permission
    )
    return agent_message.PromptRequest(
        message.agent,
        message.prompt,
        user.user_id,
        message.thread,
        message.model_dump(include={'content_block'}).get('content_block',[]),
        message.mess_id,
        message.send_at,
        context
    )

def answer_to_reply(answer:agent_message.PromptAnswer)->Reply:
    return Reply(**answer.export())

def iterator_factory(callback:AsyncGenerator[Any,Message],session:Session,user:User,wait=0.2,limit=3):
    @wraps
    async def request_generator():
        async for message in callback():
            request = message_to_request(message,session,user,limit)
            request = request.to_proto()
            yield request
            asyncio.sleep(wait)
    return request_generator()


@Service(links=[LinkDep(RedisService,to_build=True),LinkDep(MongooseService,to_build=True)])
class ChatService(BaseService):
    """Answer message with priority because of the rate limit """

    def __init__(self,configService:ConfigService,arqService:ArqIngestTaskService,settingService:SettingService,mongooseService:MongooseService,remoteAgentService:RemoteAgentService,redisService:RedisService,costService:CostService,vaultService:VaultService) -> None:
        super().__init__()
        self.mongooseService = mongooseService
        self.remoteAgentService = remoteAgentService
        self.redisService = redisService
        self.configService = configService
        self.costService = costService
        self.vaultService = vaultService
        self.settingService = settingService
        self.arqService = arqService
    
    async def end_chat(self,user:User,session:Session,thread:Thread):
        # TODO Delete current message by session and add them into a session object and summarize
        # TODO Add a job that will turn the old conversation into a knowledge Graph
        ...
    
    async def fetch_chat(self,user:User,thread:Thread):
        ...

    async def delete_chat(self,user:User,thread:Thread):
        ...

    async def interrupt(self,user:User,thread:Thread):
        ...

    async def fetch_interrupt(self,user:User,thread:Thread):
        ...
    
    async def fetch_memory(self,user:User,thread:Thread):
        ...
    
    async def stream_answer(self,generator:AsyncGenerator[Any,Message],_session:Session,_user:User,_agent:str,*args,_wait=0.5,**kwargs):
        generator = partial(generator,*args,**kwargs,wait=_wait)
        generator = iterator_factory(generator,_session,_user,wait=_wait,limit=None)
        async with self.remoteAgentService.lock(_agent) as remoteAgent:
            reply = await remoteAgent.StreamPrompt(generator)
            reply = answer_to_reply(reply)
            return reply

    async def stream_answer_stream(self,generator:AsyncGenerator[Any,Message],_session:Session,_user:User,_agent:str,*args,_wait=0.5,**kwargs):
        generator = partial(generator,*args,**kwargs)
        generator = iterator_factory(generator,_session,_user,wait=_wait,limit=None)
        async with self.remoteAgentService.lock(_agent) as remoteAgent:
            async for reply in remoteAgent.S2SPrompt(generator):
                reply = answer_to_reply(reply)
                yield reply

    async def answer(self,message:Message,session:Session,user:User):
        """Answer message with priority because of the rate limit """
        async with self.remoteAgentService.lock(message.agent) as remoteAgent:
            request = message_to_request(message,session,user)
            answer = await remoteAgent.Prompt(request)
            reply = answer_to_reply(answer)
            return reply

    async def answer_stream(self,message:Message,session:Session,user:User):
        """Answer message with priority because of the rate limit """
        async with self.remoteAgentService.lock(message.agent) as remoteAgent:
            request = message_to_request(message,session,user,)
            async for answer in remoteAgent.PromptStream(request):
                reply = answer_to_reply(answer)
                yield reply
