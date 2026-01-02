import functools
from random import randint
from typing import Any, Callable
from app.classes.step import SkipStep, Step, StepRunner
from app.utils.constant import CostConstant
from app.utils.globals import APP_MODE,ApplicationMode

DATA_TASK_REGISTRY = []

def RegisterTask(active:bool=True):

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
        async def wrapper(ctx:dict[str,Any],*args,collection_name:str=None,job_id:str=None,step:Step = None,**kwargs):

            async def refund(size):
                if step['status'] != 'running':
                    return
                if size != None:
                    await costService.refund_credits(CostConstant.DOCUMENT_CREDIT,size)
    
            if step==None:
                step = Step(current_step=None,status='start',steps=dict())
            
            costService = Get(CostService)
            fileService = Get(FileService)

            try:
                res = await func(*args,**kwargs,step=step,collection_name=collection_name,job_id=job_id)
                step['status'] = 'done'
                await asyncio.sleep(randint(5,10))
                return res
            except asyncio.CancelledError as e:
                await refund(costService,fileService,kwargs.get('size',None),step)
                raise e
            except Retry as e:
                ## append the step
                raise e
            except Exception as e:
                await refund(kwargs.get('size',None))
                raise e

        if active:
            DATA_TASK_REGISTRY.append(wrapper)
            return wrapper
        
        return func

    return decorator

@RegisterTask()
async def process_file_loader_task(ctx:dict[str,Any],file_path: str,collection_name:str,lang:str='en',content_type:str=None,job_id:str=None,size:int=None,step:Step = None):

    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)
    costService:CostService = Get(CostService)

    extension =  fileService.get_extension(file_path)
    textDataLoader = TextDataLoader(...,file_path,lang,extension,content_type)

    async with StepRunner(step,'process') as skip:
        skip()
        points = await textDataLoader.process()
        await costService.deduct_credits(CostConstant.TOKEN_CREDIT,1)
        await qdrantService.upload_points(collection_name,list(points),)

    async with StepRunner(step,'cleanup') as skip:
        skip()
        fileService.delete_tempfile(file_path)
    
    return {"job_id":job_id,"size":size,"collection_name":collection_name,"tokens":1}

@RegisterTask(False)
async def process_web_research_task(ctx:dict[str,Any],url:list[str],lang:str='en',collection_name:str=None):
    ...

@RegisterTask(False)
async def process_api_data(ctx:dict[str,Any],url:list[str]):
    ...

if APP_MODE == ApplicationMode.arq:
    
    from arq.connections import RedisSettings
    from app.classes.data_loader import TextDataLoader
    from app.services import QdrantService
    from app.services import Neo4JService
    from app.services import FileService
    from app.services.database.mongoose_service import MongooseService
    from app.services.database.redis_service import RedisService
    from app.services.vault_service import VaultService
    from app.services.cost_service import CostService
    from app.services.worker.arq_service import ArqService,QUEUE_NAME
    from app.container import Get,build_container
    import asyncio
    from arq import Retry


    build_container()
    arqService = Get(ArqService)
    
    class WorkerSettings:
        functions = DATA_TASK_REGISTRY
        redis_settings = RedisSettings.from_dsn(arqService.arq_url)
        queue_name = QUEUE_NAME
        max_jobs = 5
        allow_abort_jobs = True
        keep_result_forever = True
        retry_jobs = False
        burst = True
        max_burst_jobs = 5
    
    async def on_job_start():
        ...
    
    async def on_job_end():
        ...
    
    async def after_job_end():
        ...

    async def startup():
        ...

    async def shutdown():
        mongooseService = Get(MongooseService)
        neo4jService = Get(Neo4JService)
        redisService = Get(RedisService)

        qdrantService = Get(QdrantService)
        vaultService = Get(VaultService)

        redisService.revoke_lease()
        mongooseService.revoke_lease()
        
        vaultService.revoke_auth_token()