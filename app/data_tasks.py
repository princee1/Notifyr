import functools
from typing import Any, Callable
from app.classes.step import Step, StepRunner
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
        async def wrapper(ctx:dict[str,Any],*args,collection_name:str=None,uri:str=None,request_id:str=None,step:Step = None,_nickname:str=nickname,**kwargs):

            print(ctx)
            async def refund(size):
                if size == None:
                    return
                if step["current_step"] < DataLoaderStepIndex.PROCESS and nickname == ArqDataTaskConstant.FILE_DATA_TASK:
                    file_path = arqService.compute_data_file_upload_path(uri)
                    await arqService.enqueue_task(FILE_CLEANUP,job_id=uri, kwargs={'file_path':file_path})
                else:
                    cost = FileCost(request_id,uri).init(1,CostConstant.DOCUMENT_CREDIT)
                    cost.post_refund(FileResponseUploadModel(metadata=[UriMetadata(uri,size)]))
                    cost.balance_before = await costService.get_credit_balance(CostConstant.DOCUMENT_CREDIT)
                    await costService.refund_credits(CostConstant.DOCUMENT_CREDIT,cost.refund_cost)
                    await costService.push_bill(CostConstant.DOCUMENT_CREDIT,cost.generate_bill())
      
            if step==None:
                step = Step(current_step=None,steps=dict())
            
            costService = Get(CostService)
            redisService = Get(RedisService)
            try:
                return await func(*args,**kwargs,step=step,collection_name=collection_name,uri=uri,request_id=request_id)
            except asyncio.CancelledError as e:
                await refund(kwargs.get('size',None))
                raise e
            except Retry as e:
                raise e
            except Exception as e:
                await refund(kwargs.get('size',None))
                raise e

        if active:
            task_registry.append(wrapper)
            DATA_TASK_REGISTRY_NAME[nickname] = wrapper.__qualname__

            return wrapper if wrap else func
        else:
            return func

    return decorator

@RegisterTask(ArqDataTaskConstant.FILE_DATA_TASK,True)
async def process_file_loader_task(ctx:dict[str,Any],collection_name:str,lang:str='en',category:str=None,uri:str=None,size:int=None,step:Step = None,request_id:str=None,strategy:ParseStrategy=None,use_docling:bool=None):

    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)
    costService:CostService = Get(CostService)
    arqService:ArqDataTaskService = Get(ArqDataTaskService) 

    file_path = arqService.compute_data_file_upload_path(uri)

    extension =  fileService.get_extension(file_path)
    textDataLoader = TextDataLoader(...,file_path,lang,extension,category,strategy,use_docling)
    token = None

    async with StepRunner(step,DataLoaderStepIndex.CHECK) as skip:
        skip()
        if not await qdrantService.collection_exists(collection_name,reverse=None):
            return {"size":size,"collection_name":collection_name,"token":0,"error":True}

    async with StepRunner(step,DataLoaderStepIndex.PROCESS) as skip:
        skip()
        await textDataLoader.process()
        token = textDataLoader.compute_token()
        await qdrantService.upload_points(collection_name,list(textDataLoader.points),)
    
    async with StepRunner(step,DataLoaderStepIndex.TOKEN_COST, params=token) as skip:
        skip()
        cost = TokenCost(request_id,uri)
        cost.purchase(f'Ai token data process: {uri}',step['current_params'])
        cost.balance_before = await costService.deduct_credits(CostConstant.TOKEN_CREDIT,cost.purchase_cost)
        await costService.push_bill(CostConstant.TOKEN_CREDIT,cost.generate_bill())

    async with StepRunner(step,DataLoaderStepIndex.CLEANUP) as skip:
        skip()
        await RunAsync(fileService.delete_file)(file_path)
    
    return {"size":size,"collection_name":collection_name,"tokens":1}

@RegisterTask(ArqDataTaskConstant.WEB_DATA_TASK,False)
async def process_web_research_task(ctx:dict[str,Any],url:list[str],lang:str='en',collection_name:str=None):
    ...

@RegisterTask(ArqDataTaskConstant.API_DATA_TASK,False)
async def process_api_data(ctx:dict[str,Any],url:list[str]):
    ...

@RegisterTask(FILE_CLEANUP,True,False)
async def delete_file(ctx:dict[str,Any],file_path:str=None):
    fileService = Get(FileService)
    return await RunAsync(fileService.delete_file)(file_path)

if APP_MODE == ApplicationMode.arq:
    
    from arq.connections import RedisSettings
    from app.classes.data_loader import TextDataLoader, DataLoaderStepIndex
    from app.services import QdrantService
    from app.services import Neo4JService
    from app.services import FileService
    from app.services.database.mongoose_service import MongooseService
    from app.services.database.redis_service import RedisService
    from app.services.vault_service import VaultService
    from app.services.cost_service import CostService
    from app.services.worker.arq_service import ArqDataTaskService,QUEUE_NAME
    from app.container import Get,build_container
    import asyncio
    from arq import Retry

    build_container()
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
        ...

    @staticmethod
    async def shutdown(ctx:dict[str,Any]):
        mongooseService = Get(MongooseService)
        neo4jService = Get(Neo4JService)
        redisService = Get(RedisService)

        qdrantService = Get(QdrantService)
        vaultService = Get(VaultService)

        redisService.revoke_lease()
        mongooseService.revoke_lease()
        
        vaultService.revoke_auth_token()