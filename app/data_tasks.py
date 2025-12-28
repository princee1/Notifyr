from typing import Callable
from app.container import Get,build_container
from app.services import ConfigService
from app.services import QdrantService
from app.services import FileService
from app.services import Neo4JService
from app.services.database.mongoose_service import MongooseService
from app.services.database.redis_service import RedisService
from app.services.vault_service import VaultService
from app.utils.constant import RedisConstant
from app.utils.globals import APP_MODE,ApplicationMode

DATA_TASK_REGISTRY = []

def RegisterTask(func:Callable):
    """
    The `RegisterTask` function adds the name of a given function to a list called `DATA_TASK_REGISTRY`.
    
    :param func: The `func` parameter in the `RegisterTask` function is expected to be a callable
    object, such as a function or a method, that will be registered in the `DATA_TASK_REGISTRY` list
    :type func: Callable
    :return: The function `RegisterTask` is returning the input function `func` after appending its name
    to the `DATA_TASK_REGISTRY` list.
    """
    DATA_TASK_REGISTRY.append(func.__name__)
    return func

@RegisterTask
async def process_text_loader_task(ctx,text_path: str,collection_name:str,lang:str='en'):
    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)

    extension =  fileService.get_extension(text_path)
    textDataLoader = TextDataLoader(...,text_path,lang,extension)
    points = await textDataLoader.process()
    await qdrantService.upload_points(collection_name,list(points),)

@RegisterTask
async def process_multimedia_loader_task(ctx,video_path: str,lang:str='en'):
    qdrantService:QdrantService = Get(QdrantService)

@RegisterTask
async def process_stats_loader_task(ctx,csv_path: str,lang:str='en'):
    qdrantService:QdrantService = Get(QdrantService)


if APP_MODE == ApplicationMode.arq:
    from arq.connections import RedisSettings
    from app.classes.data_loader import TextDataLoader

    build_container()
    redisService = Get(RedisService)
    arq_url = f"redis://{redisService.db_user}:{redisService.db_password}@redis:6379/{RedisConstant.EVENT_DB}"
    
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