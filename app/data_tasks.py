import functools
from typing import Any, Callable
from app.classes.qdrant import QdrantCollectionDoesNotExist
from app.classes.step import SkipStep, Step, StepRunner
from app.models.file_model import FileResponseUploadModel, UriMetadata
from app.utils.constant import CostConstant,ArqDataTaskConstant, ParseStrategy
from app.utils.globals import APP_MODE,ApplicationMode
from app.utils.tools import RunAsync

task_registry = []
FILE_CLEANUP='file_cleanup'
DATA_TASK_REGISTRY_NAME = {}

def RegisterTask(nickname:str,active:bool=True,wrap=True):

    def decorator(func:Callable):
        """
        The `RegisterTask` function adds the name of a given function to a list called `DATA_TASK_REGISTRY`.
        
        :param func: The `func` parameter in the `RegisterTask` function is expected to be a callable
        object, such as a function or a method, that will be registered in the `DATA_TASK_REGISTRY` list
        :type func: Callable
        :return: The function `RegisterTask` is returning the input function `func` after appending its name
        to the `DATA_TASK_REGISTRY` list.
        """
    
        @functools.wraps(func)
        async def wrapper(ctx:dict[str,Any],*args,collection_name:str=None,uri:str=None,request_id:str=None,step:Step = None,_nickname:str=nickname,size:int=None,**kwargs):

            async def refund():
                if step["current_step"] < DataLoaderStepIndex.PROCESS:
                    cost = FileCost(request_id,f"arq-job@{uri}").init(1,CostConstant.DOCUMENT_CREDIT)
                    cost.post_refund(FileResponseUploadModel(metadata=[UriMetadata(uri=uri,size=size)]))
                    bill = cost.generate_bill()
                    await costService.refund_credits(CostConstant.DOCUMENT_CREDIT,cost.refund_cost,bill)
                
                if step['current_step'] < DataLoaderStepIndex.CLEANUP and nickname == ArqDataTaskConstant.FILE_DATA_TASK:
                    _step = Step(current_step=DataLoaderStepIndex.CLEANUP-1,steps={},current_params=None)
                    await func(ctx,*args,**kwargs,step=_step,collection_name=collection_name,uri=uri,request_id=request_id,size=size)
      
            if step==None:
                step = Step(current_step=0,steps={},current_params=None)
            
            costService = Get(CostService)
            redisService = Get(RedisService)
            try:
                return await func(ctx,*args,**kwargs,step=step,collection_name=collection_name,uri=uri,request_id=request_id,size=size)
            except (asyncio.CancelledError,Exception) as e:
                await refund()
                raise e
            except Retry as e:
                await arqService.update_step(uri,step,5)
                raise e

        if active:
            task_registry.append(wrapper)
            DATA_TASK_REGISTRY_NAME[nickname] = wrapper.__qualname__

            return wrapper if wrap else func
        else:
            return func

    return decorator

@RegisterTask(ArqDataTaskConstant.FILE_DATA_TASK,True)
async def process_file_loader_task(ctx:dict[str,Any],collection_name:str,lang:str='en',category:str=None,uri:str=None,size:int=None,step:Step = None,request_id:str=None,strategy:ParseStrategy=None,use_docling:bool=None,sha:str=None):

    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)
    costService:CostService = Get(CostService)
    llmProviderService:LLMProviderService = Get(LLMProviderService)
    arqService:ArqDataTaskService = Get(ArqDataTaskService)

    file_path = arqService.compute_data_file_upload_path(uri)

    extension =  fileService.get_extension(file_path)
    textDataLoader = TextDataLoader(...,file_path,lang,extension,category,strategy,use_docling)
    token = None

    async with StepRunner(step,DataLoaderStepIndex.CHECK) as skip:
        skip()
        if not await qdrantService.collection_exists(collection_name,reverse=None):
           raise QdrantCollectionDoesNotExist(collection_name)
        
    async with StepRunner(step,DataLoaderStepIndex.TOKEN_VERIFY) as skip:
        skip()
        if strategy != ParseStrategy.SEMANTIC:
            raise SkipStep()
        await costService.check_enough_credits(CostConstant.TOKEN_CREDIT,size*2)
        
    async with StepRunner(step,DataLoaderStepIndex.PROCESS) as skip:
        skip()
        await textDataLoader.process()
        token = textDataLoader.compute_token()
        step['current_params']=token
        await qdrantService.upload_points(collection_name,textDataLoader.points,)
        
    async with StepRunner(step,DataLoaderStepIndex.TOKEN_COST) as skip:
        skip()
        if strategy != ParseStrategy.SEMANTIC:
            raise SkipStep()
        cost = TokenCost(request_id,f"arq-job@{uri}")
        cost.purchase(f'Ai token data process: {uri}',1,step['current_params'])
        bill = cost.generate_bill()
        await costService.deduct_credits(CostConstant.TOKEN_CREDIT,bill)
    
    async with StepRunner(step,DataLoaderStepIndex.CLEANUP) as skip:
        skip()
        await RunAsync(fileService.delete_file)(file_path)

    return {"size":size,"collection_name":collection_name,"tokens":step['current_params']}

@RegisterTask(ArqDataTaskConstant.WEB_DATA_TASK,False)
async def process_web_research_task(ctx:dict[str,Any],url:list[str],lang:str='en',collection_name:str=None):
    ...

@RegisterTask(ArqDataTaskConstant.API_DATA_TASK,False)
async def process_api_data(ctx:dict[str,Any],url:list[str]):
    ...


if APP_MODE == ApplicationMode.arq:
    
    from arq.connections import RedisSettings
    from app.classes.data_loader import TextDataLoader, DataLoaderStepIndex
    from app.services import QdrantService
    from app.services import GraphitiService
    from app.services import LLMProviderService
    from app.services import FileService
    from app.services import MongooseService
    from app.services import RedisService
    from app.services import VaultService
    from app.services import CostService
    from app.services import ArqDataTaskService,QUEUE_NAME
    from app.container import Get,build_container
    import asyncio
    from arq import Retry

    build_container(quiet=True)

    arqService = Get(ArqDataTaskService)
    arqService.register_task(DATA_TASK_REGISTRY_NAME)

    from app.cost.file_cost import FileCost
    from app.cost.token_cost import TokenCost

    class WorkerSettings:
        functions = task_registry
        redis_settings = RedisSettings.from_dsn(arqService.arq_url)
        queue_name = QUEUE_NAME
        max_jobs = 5
        allow_abort_jobs = True
        keep_result_forever = True
        retry_jobs = False
        burst = True
        max_burst_jobs = 5
        job_completion_wait = 60
    
    @staticmethod
    async def on_job_start(ctx:dict[str,Any]):
        ...
    
    @staticmethod
    async def on_job_end(ctx:dict[str,Any]):
        """ coroutine function to run on job end"""
        ...
    
    @staticmethod
    async def after_job_end(ctx:dict[str,Any]):
        """coroutine function to run after job has ended and results have been recorded"""
        ...

    @staticmethod
    async def startup(ctx:dict[str,Any]):
        await arqService.initialize()

    @staticmethod
    async def shutdown(ctx:dict[str,Any]):
        mongooseService = Get(MongooseService)
        graphitiService = Get(graphitiService)
        redisService = Get(RedisService)

        qdrantService = Get(QdrantService)
        vaultService = Get(VaultService)

        redisService.revoke_lease()
        mongooseService.revoke_lease()
        
        vaultService.revoke_auth_token()