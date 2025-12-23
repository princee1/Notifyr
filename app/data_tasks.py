from typing import Callable
from app.container import Get,build_container
from app.services import ConfigService
from app.services import QdrantService
from app.services import Neo4JService
from app.utils.globals import APP_MODE, ApplicationMode


DATA_TASK_REGISTRY = []

def RegisterTask(func:Callable):
    DATA_TASK_REGISTRY.append(func.__name__)
    return func


if APP_MODE == ApplicationMode.arq:
    from app.services.agent.data_loader_service import DataLoaderService
    build_container()



async def startup():
    ...

async def shutdown():
    ...


@RegisterTask
async def process_video_loader_task(ctx,video_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

@RegisterTask
async def process_csv_loader_task(ctx,csv_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

@RegisterTask
async def process_pdf_loader_task(ctx,pdf_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

@RegisterTask
async def process_image_loader_task(ctx,image_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

@RegisterTask
async def process_text_loader_task(ctx,text_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

@RegisterTask
async def process_xml_loader_task(ctx,xml_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

@RegisterTask
async def process_markdown_loader_task(ctx,md_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

class WorkerSettings:
    functions = DATA_TASK_REGISTRY
    on_startup = startup
    on_shutdown = shutdown
    result_ttl = 60*60*24