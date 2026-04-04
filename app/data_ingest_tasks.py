import functools
import json
from typing import Any, Callable, List
from app.classes.crawl import CrawlState, CrawlTokenUsageReport, DigestState, MarkdownDocumentSize
from app.classes.qdrant import QdrantCollectionDoesNotExistError
from app.classes.step import SkipStep, Step, StepRunner
from app.cost.ingest_cost import MarkdownResultIngestCost
from app.errors.llm_error import LLMConfigNotConfiguredError
from app.models.crawal4ai_model import KnowledgeGraphExtractionConfig, SchemaExtractionConfig, TextsExtractionConfig
from app.models.file_model import FileResponseUploadModel, UriMetadata
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.profile_service import ProfileService
from app.utils.constant import CostConstant,ArqDataTaskConstant, ParseStrategy
from app.utils.globals import APP_MODE,ApplicationMode
from app.utils.helper import uuid_v1_mc
from app.utils.tools import RunAsync
from app.models.ingest_model import ResearchDataIngestModel, VectorConfig,KGraphConfig, WebCrawlingDataIngestModel

task_registry = []
FILE_CLEANUP='file_cleanup'
DATA_TASK_REGISTRY_NAME = {}

def RegisterTask(nickname:str,active:bool=True,wrap=True):


    match nickname:
        case ArqDataTaskConstant.FILE_DATA_TASK:
            async def refund(step:Step,uri:str,request_id:str,size:int,state:dict,func:Callable,ctx:dict[str,Any],*args,**kwargs):
                costService = Get(CostService)
                redisService = Get(RedisService)

                if step["current_step"] < FileIngestionStepIndex.PROCESS:
                    cost = FileCost(request_id,f"arq-job@{uri}").init(1,CostConstant.DOCUMENT_CREDIT)
                    cost.post_refund(FileResponseUploadModel(metadata=[UriMetadata(uri=uri,size=size)]))
                    bill = cost.generate_bill()
                    await costService.refund_credits(CostConstant.DOCUMENT_CREDIT,cost.refund_cost,bill)
                
                if step['current_step'] < FileIngestionStepIndex.CLEANUP:
                    _step = Step(current_step=FileIngestionStepIndex.CLEANUP-1,steps={},current_params=None)
                    await func(ctx,*args,**kwargs,step=_step,uri=uri,request_id=request_id,size=size,state=state)
        
        case ArqDataTaskConstant.API_DATA_TASK:
            async def refund():
                ...
            
        case ArqDataTaskConstant.CRAWL_DATA_TASK:
            async def refund():
                ...
        
        case ArqDataTaskConstant.RESEARCH_DATA_TASK:
            async def refund():
                ...
        
        case _:
            ...

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
        async def wrapper(ctx:dict[str,Any],*args,uri:str=None,request_id:str=None,step:Step = None,state:dict=None,_nickname:str=nickname,size:int=None,**kwargs):
      
            if step==None:
                step = Step(current_step=0,steps={},current_params=None)            
            try:
                vector_config = kwargs.get('vector_config',None)
                graph_config = kwargs.get('graph_config',None)

                if vector_config != None:
                    vector_config = VectorConfig(**vector_config)
                
                if graph_config != None:
                    graph_config = KGraphConfig(**graph_config)

                return await func(ctx,*args,**kwargs,vector_config=vector_config,graph_config=graph_config,step=step,uri=uri,request_id=request_id,size=size,state=state)
            
            except Retry as e:
                await arqService.update_job_kwargs(uri,{'step':step},5)
                await arqService.update_job_kwargs(uri,{'state':state},5)
                raise e
            
            except (asyncio.CancelledError,Exception) as e:
                await refund()
                raise e

        if active:
            task_registry.append(wrapper)
            DATA_TASK_REGISTRY_NAME[nickname] = wrapper.__qualname__

            return wrapper if wrap else func
        else:
            return func

    return decorator


@RegisterTask(ArqDataTaskConstant.FILE_DATA_TASK,True)
async def process_file_loader_task(ctx:dict[str,Any],vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,lang:str='en',uri:str=None,size:int=None,step:Step = None,request_id:str=None,strategy:ParseStrategy=None,use_docling:bool=None,sha:str=None,state:dict=None):

    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)
    graphitiService:GraphitiService = Get(GraphitiService)
    costService:CostService = Get(CostService)
    arqService:ArqIngestTaskService = Get(ArqIngestTaskService)

    file_path = arqService.compute_data_file_upload_path(uri)

    extension =  fileService.get_extension(file_path)
    textDataLoader = TextDataLoader(qdrantService.embedding_parse,file_path,lang,extension,vector_config.category,strategy,use_docling)
    token = None

    async with StepRunner(step,FileIngestionStepIndex.CHECK) as skip:
        skip()
        if vector_config != None:
            if not await qdrantService.collection_exists(vector_config.collection_name,reverse=None):
                raise QdrantCollectionDoesNotExistError(vector_config.collection_name)
            
    async with StepRunner(step,FileIngestionStepIndex.TOKEN_VERIFY) as skip:
        skip()
        if strategy != ParseStrategy.SEMANTIC:
            raise SkipStep()
        await costService.check_enough_credits(CostConstant.TOKEN_CREDIT,size*2)
        
    async with StepRunner(step,FileIngestionStepIndex.PROCESS) as skip:
        skip()
        await textDataLoader.process()
        token = textDataLoader.compute_token()
        step['current_params']=token

        if vector_config != None:
            await qdrantService.upload_points(vector_config.collection_name,textDataLoader.chunks)
        
        if graph_config != None:
            for chunk in textDataLoader.chunks:
                await graphitiService.add_chunk_episode(chunk,graph_config.instruction,graph_config.entities,graph_config.edges)

    async with StepRunner(step,FileIngestionStepIndex.TOKEN_COST) as skip:
        skip()
        if strategy != ParseStrategy.SEMANTIC:
            raise SkipStep()
        cost = TokenCost(request_id,f"arq-job@{uri}")
        cost.purchase(f'Ai token data process: {uri}',1,step['current_params'])
        bill = cost.generate_bill()
        await costService.deduct_credits(CostConstant.TOKEN_CREDIT,bill)
    
    async with StepRunner(step,FileIngestionStepIndex.CLEANUP) as skip:
        skip()
        await RunAsync(fileService.delete_file)(file_path)

    return {"size":size,"collection_name":vector_config.collection_name,"tokens":step['current_params']}


@RegisterTask(ArqDataTaskConstant.API_DATA_TASK,False)
async def process_api_data(ctx:dict[str,Any],lang:str='en',vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,size:int=None,step:Step = None,request_id:str=None,state:dict=None,**kwargs):

    qdrantService:QdrantService = Get(QdrantService)
    graphitiService:GraphitiService = Get(GraphitiService)
    costService:CostService = Get(CostService)
    arqService:ArqIngestTaskService = Get(ArqIngestTaskService)


@RegisterTask(ArqDataTaskConstant.RESEARCH_DATA_TASK,False)
async def process_research_task(ctx:dict[str,Any],vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,size:int=None,lang:str='en',step:Step = None,request_id:str=None,state:dict=None,uri:str=None,**kwargs):

    qdrantService:QdrantService = Get(QdrantService)
    graphitiService:GraphitiService = Get(GraphitiService)
    llMProviderService:LLMProviderService = Get(LLMProviderService)
    costService:CostService = Get(CostService)
    fileService:FileService = Get(FileService)
    arqService:ArqIngestTaskService = Get(ArqIngestTaskService)
    customService:CustomService = Get(CustomService)
    configService:ConfigService = Get(ConfigService)

    crawlLLMProvider = llMProviderService.crawl_config.get('llmConfig',None)
    if not crawlLLMProvider:
        raise LLMConfigNotConfiguredError('crawl_config')

    researchLLMProvider = llMProviderService.research_config.get('llmConfig',None)
    if not researchLLMProvider:
        raise LLMConfigNotConfiguredError('research_config')

    crawlLLMProvider = llMProviderService.MiniServiceStore.get(crawlLLMProvider)
    researchLLMProvider = llMProviderService.MiniServiceStore.get(researchLLMProvider)

    async def digest_callback(digest_state:DigestState):
        state.clear()
        state.update(digest_state)
        await arqService.update_job_kwargs(uri,{'state':state},5)

    researcher =  ResearchIngestion(
        researchTask=ResearchDataIngestModel(
            lang=lang,
            vector_config=vector_config,
            graph_config=graph_config,
            **kwargs
        ),
        digest_callback=digest_callback,
        research_llm_config=researchLLMProvider.crawl_llm,
        crawl_llm_config=crawlLLMProvider.crawl_llm,
        base_dir=f"{configService.DATA_INGESTION_DIR}crawl4ai/",
    )

    await researcher.initialize_folders()
    await researcher.initialize_config()

    async with StepRunner(step,ResearchIngestionStepIndex.CHECK) as skip:
        skip()
        if vector_config != None:
            if not await qdrantService.collection_exists(vector_config.collection_name,reverse=None):
                raise QdrantCollectionDoesNotExistError(vector_config.collection_name)
        if graph_config != None:
            ... # check graph edges/entities existence
    
    async with StepRunner(step,ResearchIngestionStepIndex.TOKEN_VERIFY) as skip:
        skip()
        await costService.check_enough_credits(CostConstant.TOKEN_CREDIT,size*10)
    
    async with StepRunner(step,ResearchIngestionStepIndex.QUERY_LOOKUP) as skip:
        skip()
        ... # lookup for query in vector db to refine research question
    
    async with StepRunner(step,ResearchIngestionStepIndex.LINKS_LOOKUP) as skip:
        skip()
        await researcher.start()
        await researcher.crawl()
        await researcher.close()
        ... # lookup for relevant links in vector db
    
    async with StepRunner(step,ResearchIngestionStepIndex.LOOKUP_COST) as skip:
        skip()
        ... # compute lookup cost and deduct credits
    
    async with StepRunner(step,ResearchIngestionStepIndex.RESEARCH) as skip:
        skip()
        await researcher.start()
        await researcher.research()
        
        await researcher.close()
    
    async with StepRunner(step,ResearchIngestionStepIndex.RESULT_COST) as skip:
        skip()
        ... # compute research result cost and deduct credits
    
    async with StepRunner(step,ResearchIngestionStepIndex.CLEANUP) as skip:
        skip()
        

@RegisterTask(ArqDataTaskConstant.CRAWL_DATA_TASK,False)
async def process_website_crawling(ctx:dict[str,Any],vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,size:int=None,step:Step = None,request_id:str=None,uri:str=None,state:CrawlState=None,**kwargs):
    qdrantService:QdrantService = Get(QdrantService)
    configService:ConfigService = Get(ConfigService)
    llMProviderService:LLMProviderService = Get(LLMProviderService)
    profileService:ProfileService = Get(ProfileService)
    graphitiService:GraphitiService = Get(GraphitiService)
    costService:CostService = Get(CostService)
    arqService:ArqIngestTaskService = Get(ArqIngestTaskService)
    customService:CustomService = Get(CustomService)
 
    schema = None
    results = []

    async def deep_crawl_callback(dc_state:dict):
        state['deep_crawl'] = dc_state
        await arqService.update_job_kwargs(uri,{'state':state},5)
    
    crawlLLMProvider = llMProviderService.crawl_config.get('llmConfig',None)
    if not crawlLLMProvider:
        raise LLMConfigNotConfiguredError('crawl_config')

    llmProvider = llMProviderService.MiniServiceStore.get(crawlLLMProvider)
    ingestTask = WebCrawlingDataIngestModel(vector_config=vector_config,graph_config=graph_config,**kwargs)
    
    if isinstance(ingestTask.extraction,SchemaExtractionConfig):
        schema = ingestTask.extraction.schema
        schema = customService.to_schemas([schema])[schema]

    crawler = WebCrawlerIngestion(
        ingestTask=ingestTask,
        crawl_state=state,
        crawl_llm_config=llmProvider.crawl_llm,
        dc_state_callback=deep_crawl_callback,
        base_dir=f"{configService.DATA_INGESTION_DIR}crawl4ai/",
        schema=schema
    )

    async with StepRunner(step,CrawlIngestionStepIndex.CHECK) as skip:
        skip()
        if vector_config != None:
            if not await qdrantService.collection_exists(vector_config.collection_name,reverse=None):
                raise QdrantCollectionDoesNotExistError(vector_config.collection_name)
        if graph_config != None:
            ... # check graph edges/entities existence
    
    async with StepRunner(step,CrawlIngestionStepIndex.TOKEN_VERIFY) as skip:
        skip()
        await costService.check_enough_credits(CostConstant.TOKEN_CREDIT,size*5)
    
    async with StepRunner(step,CrawlIngestionStepIndex.CRAWL) as skip:
        skip()

        await crawler.initialize_folders()
        await crawler.initialize_config()

        await crawler.start()

        async for result in crawler.crawl():
            if not result.success:
                continue

            if isinstance(crawler.ingestTask.extraction,TextsExtractionConfig):
                if not result.chunks:
                    continue

                if vector_config != None:
                    for chunk in result.chunks:
                        chunk.vector = await qdrantService.embed_query(chunk.payload['text'])
                    await qdrantService.upload_points(vector_config.collection_name,result.chunks,True,)
                    
                if graph_config != None:
                    for chunk in result.chunks:
                        await graphitiService.add_chunk_episode(
                            chunk,
                            graph_config.instruction,
                            entities=graph_config.entities,
                            edges=graph_config.edges,
                            description=result.description
                        )
            elif isinstance(crawler.ingestTask.extraction,SchemaExtractionConfig):

                if graph_config == None:
                    continue

                if not result.extracted_content:
                    continue

                for item in result.extracted_content: 
                    if not item:
                        continue

                    await graphitiService.add_content_episode(
                        source=result.url,
                        entities=graph_config.entities,
                        edges=graph_config.edges,
                        name = item.get('title',None),
                        description = result.description,
                        body = json.loads(item.get('content',None)),
                        domain = graph_config.domain,
                        instruction = graph_config.instruction,
                        uuid = f"{item.get('id',None)}@{uuid_v1_mc()}"
                    )
            elif isinstance(crawler.ingestTask.extraction,KnowledgeGraphExtractionConfig):
                if not result.markdown_content:
                    continue

                uuid = f"{uuid_v1_mc()}"
                await graphitiService.add_content_episode(
                    name=result.title,
                    source=result.url,
                    description=result.description,
                    body=result.markdown_content,
                    uuid=uuid,
                    domain=graph_config.domain,
                    instruction=graph_config.instruction,
                    entities=graph_config.entities,
                    edges=graph_config.edges
                )
        step['current_params']={'token':crawler.token_usage(),'document':crawler.documents}
        await crawler.close()
      
    async with StepRunner(step,CrawlIngestionStepIndex.TOTAL_COST) as skip:
        skip()
        ingestTask.compute_size()
        issuer = f"arq-job@{uri}"

        url_size = ingestTask._url_size or 0
        pdf_size = ingestTask.pdf_size or 0

        token:CrawlTokenUsageReport = step['current_params']['token']
        document:List[MarkdownDocumentSize] = step['current_params']['document']

        tokenCost = TokenCost(request_id,issuer)
        markdownCost = MarkdownResultIngestCost(request_id,issuer)
        markdownCost.init(1,'document','Crawl Credit Refund','full','Crawl')

        for usage in token.tokens:
            tokenCost.purchase(token.model,token.provider,token.provider_id,'input',f"Crawl token usage for {usage['step']} tokens",usage['input_tokens'])
            tokenCost.purchase(token.model,token.provider,token.provider_id,'output',f"Crawl token usage for {usage['step']} tokens",usage['output_tokens'])

        token_bill = tokenCost.generate_bill()
        await costService.deduct_credits(CostConstant.TOKEN_CREDIT,token_bill)
        
        markdownCost.post_refund(document,ingestTask.db_config,url_size,pdf_size)
        document_bill = markdownCost.generate_bill()
        await costService.refund_credits(CostConstant.DOCUMENT_CREDIT,document_bill)
        
    async with StepRunner(step,CrawlIngestionStepIndex.CLEANUP) as skip:
        skip()
    
    return 


if APP_MODE == ApplicationMode.arq:
    
    from arq.connections import RedisSettings

    from app.ingestion.file_ingestion import TextDataLoader, FileIngestionStepIndex
    from app.ingestion.crawl_ingestion import CrawlIngestionStepIndex, WebCrawlerIngestion
    from app.ingestion.research_ingestion import ResearchIngestion, ResearchIngestionStepIndex

    from app.services import QdrantService
    from app.services import GraphitiService
    from app.services import LLMProviderService
    from app.services import FileService
    from app.services import MongooseService
    from app.services import RedisService
    from app.services import VaultService
    from app.services import CostService
    from app.services.worker.arq_service import ArqIngestTaskService,QUEUE_NAME

    from app.container import Get,build_container
    import asyncio
    from arq import Retry

    build_container(quiet=True)

    arqService = Get(ArqIngestTaskService)
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
        graphitiService = Get(GraphitiService)
        redisService = Get(RedisService)
        qdrantService = Get(QdrantService)
        
        vaultService = Get(VaultService)

        redisService.revoke_lease()
        mongooseService.revoke_lease()
        graphitiService.revoke_lease()
        
        vaultService.revoke_auth_token()