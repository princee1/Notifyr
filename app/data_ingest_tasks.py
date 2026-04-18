import functools
import json
from typing import Any, Callable, List
from app.classes.cost_definition import MarkdownCostDefinition
from app.classes.crawl import CrawlState, CrawlTokenUsageReport, DigestState, MarkdownDocumentSize, SchemaNotFoundError
from app.classes.qdrant import QdrantCollectionDoesNotExistError
from app.classes.step import SkipStep, Step, StepRunner
from app.errors.ingest_error import IngestTaskNotSupportedError
from app.errors.llm_error import LLMConfigNotConfiguredError
from app.models.crawal4ai_model import KnowledgeGraphExtractionConfig, SchemaExtractionConfig, TextsExtractionConfig
from app.models.file_model import FileResponseUploadModel, UriMetadata
from app.services.agent.llm_provider_service import LLMProviderMiniService
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.profile_service import ProfileService
from app.utils.constant import CostConstant,ArqDataTaskConstant, Crawl4AIConstant, ParseStrategy
from app.utils.globals import APP_MODE,ApplicationMode
from app.utils.helper import slice_dict, uuid_v1_mc
from app.utils.tools import RunAsync
from app.models.ingest_model import ResearchDataIngestModel, VectorConfig,KGraphConfig, WebCrawlingDataIngestModel

task_registry = []
FILE_CLEANUP='file_cleanup'
CRAWL_PROVIDER_KEY='crawl_llm'
RESEARCH_PROVIDER_KEY='research_llm'
DATA_TASK_REGISTRY_NAME = {}
BASE_JOB_KWARGS_KEYS = {'uri','size','_nickname'}

###################################################################################################################
###################################################################################################################

async def verify_token_credit(**kwargs):
        costService = Get(CostService)  
        qdrantService = Get(QdrantService)

        size = kwargs.get('size')
        _nickname = kwargs.get('_nickname')
        vector_config = kwargs.get('vector_config',None)
        graph_config = kwargs.get('graph_config',None)

        match _nickname:
            case ArqDataTaskConstant.CRAWL_DATA_TASK:
                size*=30
            case ArqDataTaskConstant.RESEARCH_DATA_TASK:
                size*=20
            case ArqDataTaskConstant.FILE_DATA_TASK:
                strategy = kwargs.get('strategy',ParseStrategy.STRUCTURED)
                size *= 5 if strategy != ParseStrategy.SEMANTIC else 10
            case _:
                raise IngestTaskNotSupportedError(_nickname)

        factor = 0
        if vector_config != None:
            factor +=1
            if not await qdrantService.collection_exists(vector_config['collection_name'],reverse=None):
                raise QdrantCollectionDoesNotExistError(vector_config['collection_name'])
        if graph_config != None:
            factor+=1
            ... # check graph edges/entities existence
            
        await costService.check_enough_credits(CostConstant.TOKEN_CREDIT,size*factor)
    
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

        case ArqDataTaskConstant.CRAWL_DATA_TASK:
            async def refund():
                ...

        case ArqDataTaskConstant.RESEARCH_DATA_TASK:
            async def refund():
                ...
        case _:
            raise IngestTaskNotSupportedError(nickname)

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
                
                issuer = f"arq-job@{uri}"
                ctx['_nickname'] = _nickname
                
                await verify_token_credit(vector_config=vector_config,graph_config=graph_config,size=size,_nickname=nickname,strategy=kwargs.get('strategy',ParseStrategy.STRUCTURED))
                return await func(ctx,*args,**kwargs,vector_config=vector_config,graph_config=graph_config,step=step,uri=uri,request_id=request_id,size=size,state=state,issuer=issuer)
            
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

###################################################################################################################
###################################################################################################################

@RegisterTask(ArqDataTaskConstant.FILE_DATA_TASK,True)
async def process_file_loader_task(ctx:dict[str,Any],vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,lang:str='en',uri:str=None,size:int=None,step:Step = None,request_id:str=None,strategy:ParseStrategy=None,use_docling:bool=None,sha:str=None,state:dict=None,issuer:str=None):

    qdrantService:QdrantService = Get(QdrantService)
    fileService:FileService = Get(FileService)
    graphitiService:GraphitiService = Get(GraphitiService)
    costService:CostService = Get(CostService)
    arqService:ArqIngestTaskService = Get(ArqIngestTaskService)

    file_path = arqService.compute_data_file_upload_path(uri)
    extension =  fileService.get_extension(file_path)
    textDataLoader = TextDataLoader(qdrantService.embedding_parse,file_path,lang,extension,vector_config.category,strategy,use_docling)
    token = None
    
    async with StepRunner(step,FileIngestionStepIndex.PROCESS) as skip:
        skip()
        await textDataLoader.process()
        token = textDataLoader.compute_token()
        step['current_params']=token

        if vector_config != None:
            await qdrantService.upload_points(vector_config.collection_name,textDataLoader.chunks)
        
        if graph_config != None:
            for chunk in textDataLoader.chunks:
                await graphitiService.add_chunk_episode(chunk,graph_config.instruction,graph_config.entities,graph_config.edges,graph_config.description)

    async with StepRunner(step,FileIngestionStepIndex.TOKEN_COST) as skip:
        skip()
        if strategy != ParseStrategy.SEMANTIC:
            raise SkipStep()
        cost = TokenCost(request_id,issuer)
        cost.purchase(f'Ai token data process: {uri}',1,step['current_params'])
        bill = cost.generate_bill()
        await costService.deduct_credits(CostConstant.TOKEN_CREDIT,bill)
    
    async with StepRunner(step,FileIngestionStepIndex.CLEANUP) as skip:
        skip()
        await RunAsync(fileService.delete_file)(file_path)

    return {"size":size,"collection_name":vector_config.collection_name,"tokens":step['current_params']}

@RegisterTask(ArqDataTaskConstant.CRAWL_DATA_TASK,False)
async def process_website_crawling(ctx:dict[str,Any],vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,size:int=None,lang:str='en',step:Step = None,request_id:str=None,uri:str=None,state:CrawlState=None,issuer:str=None,**kwargs):

    qdrantService:QdrantService = Get(QdrantService)
    configService:ConfigService = Get(ConfigService)
    fileService:FileService = Get(FileService)
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
    
    ingestTask = WebCrawlingDataIngestModel(vector_config=vector_config,graph_config=graph_config,lang=lang,name=uri,**slice_dict(kwargs,['subject'],'exclude'))
    
    if isinstance(ingestTask.extraction,SchemaExtractionConfig):
        schema = ingestTask.extraction.custom_schema
        schema = customService.to_schemas([schema]).get(schema,None)
        if not schema:
            raise SchemaNotFoundError(ingestTask.extraction.custom_schema)
        
    markdownMaxDef:MarkdownCostDefinition = costService.fetch_definition('crawl',MarkdownCostDefinition(max_html_mb=2,max_pdf_mb=10))
    markdownMaxDef['max_html_mb'] = fileService.bytes_conversion(markdownMaxDef['max_html_mb'],'mb','b')
    markdownMaxDef['max_pdf_mb'] = fileService.bytes_conversion(markdownMaxDef['max_pdf_mb'],'mb','b')

    crawlLLMProvider:LLMProviderMiniService = ctx[CRAWL_PROVIDER_KEY]

    crawler = WebCrawlerIngestion(
        ingestTask=ingestTask,
        crawl_state=state,
        crawl_llm_config=crawlLLMProvider.crawl_llm,
        dc_state_callback=deep_crawl_callback,
        base_dir=f"{configService.DATA_INGESTION_DIR}{Crawl4AIConstant.INGEST_PARENT_DIR}/",
        schema=schema,
        markdownCostDefinition=markdownMaxDef,
    )
    
    async with StepRunner(step,CrawlIngestionStepIndex.CRAWL) as skip:
        skip()
        await crawler.initialize_config()
        await crawler.start()

        async for result in crawler.crawl():
            if not result.success:
                continue

            if isinstance(crawler.ingestTask.extraction,TextsExtractionConfig):
                if not result.chunks:
                    continue

                for chunk in result.chunks:
                    if vector_config != None:
                        chunk.vector = await qdrantService.embed_query(chunk.payload['text'])

                    if graph_config != None:
                        await graphitiService.add_chunk_episode(
                            chunk,
                            graph_config.instruction,
                            entities=graph_config.entities,
                            edges=graph_config.edges,
                            description=result.description
                        )

                if vector_config !=None:
                    await qdrantService.upload_points(vector_config.collection_name,result.chunks,True,)
                              
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

@RegisterTask(ArqDataTaskConstant.RESEARCH_DATA_TASK,False)
async def process_research_task(ctx:dict[str,Any],vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,size:int=None,lang:str='en',step:Step = None,request_id:str=None,state:dict=None,uri:str=None,issuer:str=None,**kwargs):

    qdrantService:QdrantService = Get(QdrantService)
    graphitiService:GraphitiService = Get(GraphitiService)
    costService:CostService = Get(CostService)
    fileService:FileService = Get(FileService)
    arqService:ArqIngestTaskService = Get(ArqIngestTaskService)
    customService:CustomService = Get(CustomService)
    configService:ConfigService = Get(ConfigService)
    
    async def digest_callback(digest_state:DigestState):
        state.clear()
        state.update(digest_state)
        await arqService.update_job_kwargs(uri,{'state':state},5)
    
    researchLLMProvider:LLMProviderMiniService = ctx[RESEARCH_PROVIDER_KEY]
    crawlLLMProvider:LLMProviderMiniService = ctx[CRAWL_PROVIDER_KEY]

    researcher =  ResearchIngestion(
        researchTask=ResearchDataIngestModel(lang=lang,vector_config=vector_config,graph_config=graph_config,lang=lang,name=uri,**slice_dict(kwargs,['subject'],'exclude')),
        digest_callback=digest_callback,
        research_llm_config=researchLLMProvider.crawl_llm,
        crawl_llm_config=crawlLLMProvider.crawl_llm,
        base_dir=f"{configService.DATA_INGESTION_DIR}crawl4ai/",
    )

    await researcher.initialize_config()

    async with StepRunner(step,ResearchIngestionStepIndex.QUERY_EXPANSION) as skip:
        skip()
        concepts = await researcher.query_expansion()
        step['current_params'] = concepts

    async with StepRunner(step,ResearchIngestionStepIndex.LINKS_LOOKUP) as skip:
        skip()
        urls = {}
        concepts = step['current_params']
        researcher.set_crawl_task(concepts)
    
        await researcher.start()
        async for result in researcher.crawl():
            if not result.success:
                continue

        await researcher.close()
        step['currents_params'] = {
            'urls':urls,
            'token':researcher.token_usage()
        }
    
    async with StepRunner(step,ResearchIngestionStepIndex.LOOKUP_COST) as skip:
        skip()
        token:CrawlTokenUsageReport = step['current_params']['token']
        tokenCost = TokenCost(request_id,issuer)

        for usage in token.tokens:
            tokenCost.purchase(token.model,token.provider,token.provider_id,'input',f"Crawl token usage for {usage['step']} tokens",usage['input_tokens'])
            tokenCost.purchase(token.model,token.provider,token.provider_id,'output',f"Crawl token usage for {usage['step']} tokens",usage['output_tokens'])

        token_bill = tokenCost.generate_bill()
        await costService.deduct_credits(CostConstant.TOKEN_CREDIT,token_bill)
        step['current_params'] = {}

    async with StepRunner(step,ResearchIngestionStepIndex.RESEARCH) as skip:
        skip()
        researcher.clear_cost()
        await researcher.start()
        async for result in researcher.research():
            ...

            if graph_config != None:
                graphitiService.add_content_episode()

        await researcher.close()
        step['current_params']['token'] = researcher.token_usage()
        step['current_params']['document']
    
    async with StepRunner(step,ResearchIngestionStepIndex.RESULT_COST) as skip:
        skip()
        token:CrawlTokenUsageReport = step['current_params']['token']
        document:List[MarkdownDocumentSize] = step['current_params']['document']
        ... # compute research result cost and deduct credits
    
    async with StepRunner(step,ResearchIngestionStepIndex.CLEANUP) as skip:
        skip()
        
if False:
    @RegisterTask(ArqDataTaskConstant.API_DATA_TASK,False)
    async def process_api_data(ctx:dict[str,Any],lang:str='en',vector_config:VectorConfig|None=None,graph_config:KGraphConfig|None = None,size:int=None,step:Step = None,request_id:str=None,state:dict=None,**kwargs):

        qdrantService:QdrantService = Get(QdrantService)
        graphitiService:GraphitiService = Get(GraphitiService)
        costService:CostService = Get(CostService)
        arqService:ArqIngestTaskService = Get(ArqIngestTaskService)

###################################################################################################################
###################################################################################################################

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
    from app.services import LoggerService
    from app.services import SystemService
    from app.services.worker.arq_service import ArqIngestTaskService,QUEUE_NAME

    from app.container import Get,build_container
    import asyncio
    from arq import Retry

    build_container(quiet=True)
    
    arqService = Get(ArqIngestTaskService)
    arqService.register_task(DATA_TASK_REGISTRY_NAME)

    from app.cost.file_cost import FileCost
    from app.cost.token_cost import TokenCost
    from app.cost.ingest_cost import MarkdownResultIngestCost

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
        job_id:str = ctx['job_id']

    @staticmethod
    async def on_job_end(ctx:dict[str,Any]):
        job_id:str = ctx['job_id']

    @staticmethod
    async def after_job_end(ctx:dict[str,Any]):
        """coroutine function to run after job has ended and results have been recorded"""
        job_id = ctx['job_id']
        nickname:str = ctx['_nickname']
        match nickname:
            case ArqDataTaskConstant.CRAWL_DATA_TASK:
                await arqService.update_job_kwargs(job_id,data=BASE_JOB_KWARGS_KEYS.union(('urls','subject')),mode='include')
                
            case ArqDataTaskConstant.FILE_DATA_TASK:
                await arqService.update_job_kwargs(job_id,data=BASE_JOB_KWARGS_KEYS.union(('sha',)),mode='include')
                
            case ArqDataTaskConstant.RESEARCH_DATA_TASK:
                await arqService.update_job_kwargs(job_id,data=BASE_JOB_KWARGS_KEYS.union(('query',)),mode='include')
            
            case _:
                raise IngestTaskNotSupportedError(nickname)
                
    @staticmethod
    async def startup(ctx:dict[str,Any]):
        llMProviderService = Get(LLMProviderService)
        fileService = Get(FileService)

        crawlLLMProvider = llMProviderService.crawl_config.get('llmConfig',None)
        researchLLMProvider = llMProviderService.research_config.get('llmConfig',None)

        if ArqDataTaskConstant.CRAWL_DATA_TASK in DATA_TASK_REGISTRY_NAME or ArqDataTaskConstant.RESEARCH_DATA_TASK in DATA_TASK_REGISTRY_NAME:
            if not crawlLLMProvider:
                raise LLMConfigNotConfiguredError('crawl_config')
            crawlLLMProvider = llMProviderService.MiniServiceStore.get(crawlLLMProvider)
            ctx[CRAWL_PROVIDER_KEY] = crawlLLMProvider

        if ArqDataTaskConstant.RESEARCH_DATA_TASK in DATA_TASK_REGISTRY_NAME:
            if not researchLLMProvider:
                raise LLMConfigNotConfiguredError('research_config')
            researchLLMProvider = llMProviderService.MiniServiceStore.get(researchLLMProvider)
            ctx[RESEARCH_PROVIDER_KEY] = researchLLMProvider

        fileService.init_crawl4ai_folders()
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

###################################################################################################################
###################################################################################################################
