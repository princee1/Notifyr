from app.container import Get,build_container
from app.services import ConfigService
from app.services import QdrantService
from app.services import Neo4JService
from app.utils.globals import APP_MODE, ApplicationMode


if APP_MODE == ApplicationMode.arq:
    from app.services.agent.data_loader_service import DataLoaderService
    build_container()


async def process_video_loader_task(ctx,video_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

async def process_csv_loader_task(ctx,csv_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

async def process_pdf_loader_task(ctx,pdf_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

async def process_image_loader_task(ctx,image_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

async def process_text_loader_task(ctx,text_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

async def process_xml_loader_task(ctx,xml_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)

async def process_markdown_loader_task(ctx,md_path: str):
    data_loader_service:DataLoaderService = Get(DataLoaderService)


