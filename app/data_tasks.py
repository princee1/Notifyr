from typing import Callable
from app.classes.arq_worker import ArqWorker
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
        if active:
            DATA_TASK_REGISTRY.append(func.__name__)
        return func
    
    return decorator

@RegisterTask()
async def process_file_loader_task(ctx,file_path: str,collection_name:str,lang:str='en',content_type:str=None):
    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)

    extension =  fileService.get_extension(file_path)
    
    textDataLoader = TextDataLoader(...,file_path,lang,extension,content_type)
    points = await textDataLoader.process()
    await qdrantService.upload_points(collection_name,list(points),)
    
    return 

@RegisterTask(False)
async def process_web_research_task(ctx,url:list[str],lang:str='en'):
    ...

@RegisterTask(False)
async def process_api_data(ctx,url:list[str]):
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
    from app.container import Get,build_container

    build_container()

    redisService = Get(RedisService)
    arq_url = ArqWorker.create_arq_url(redisService.db_user,redisService.db_password)
    
    class WorkerSettings:
        functions = DATA_TASK_REGISTRY
        result_ttl = 60*60*24
        redis_settings = RedisSettings.from_dsn(arq_url)

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