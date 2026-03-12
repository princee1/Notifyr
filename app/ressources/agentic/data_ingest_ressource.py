from typing import Annotated, List
from fastapi import Depends, File, HTTPException, Request, Response, UploadFile,status
from app.classes.auth_permission import AuthPermission, Role
from app.container import Get, InjectInMethod
from app.cost.file_cost import FileCost
from app.cost.ingest_cost import FileIngestCost, WebIngestCost
from app.decorators.guards import ArqDataTaskGuard, DataIngestDatabaseGuard, UploadFilesGuard
from app.decorators.handlers import AgenticHandler, ArqHandler, AsyncIOHandler, CostHandler, DataIngestHandler, FileHandler, MiniServiceHandler, PydanticHandler, RedisHandler, ServiceAvailabilityHandler, UploadFileHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import  DataClassToDictPipe, MerchantPipe, MiniServiceInjectorPipe, QueryToModelPipe, update_status_upon_no_metadata_pipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, IncludeRessource, PingService, Throttle, UseGuard, UseHandler, UseInterceptor, UsePermission, UsePipe, UseRoles, UseServiceLock
from app.depends.class_dep import FileDataIngestQuery
from app.depends.dependencies import get_auth_permission, get_request_id
from app.depends.funcs_dep import get_profile
from app.manager.broker_manager import Broker
from app.manager.merchant_manager import Merchant
from app.services.agent.llm_provider_service import LLMProviderService, VerifyLLMConfig
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.redis_service import RedisService
from app.services.file.file_service import FileService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.setting_service import SettingService
from app.services.vault_service import VaultService
from app.decorators.permissions import JWTRouteHTTPPermission, ProfilePermission
from app.definition._ressource import UseLimiter
from app.services.worker.arq_service import ArqIngestTaskService, JobAlreadyExistsError, JobInProgressError,JobStatus, UnexpectedJobStatusError
from app.models.ingest_model import (
    AbortedJobResponse,
    WebCrawlingDataIngestModel,
    IngestDataUriMetadata,
    EnqueueResponse,
    FileUploadIngestEnqueueResponse,
    FileUploadDataIngestModel,
)
from app.models.file_model import  FileResponseUploadModel, UploadError
from app.data_tasks import DATA_TASK_REGISTRY_NAME
from app.utils.constant import ArqDataTaskConstant, CostConstant
from app.utils.tools import RunInThreadPool
from app.depends.variables import force_update_query


@UseHandler(ArqHandler,ServiceAvailabilityHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('jobs',)
class JobArqRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,arqService:ArqIngestTaskService,fileService:FileService,settingService:SettingService):
        super().__init__(None,None)
        self.arqService = arqService
        self.configService = configService
        self.fileService = fileService
        self.settingService = settingService
    
    @UseHandler(AsyncIOHandler)
    @PingService([ArqIngestTaskService])
    @UseServiceLock(ArqIngestTaskService,lockType='reader')
    @UsePipe(DataClassToDictPipe(),before=False)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def get_queued_jobs(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.arqService.get_queued_jobs()
        
    @UseHandler(AsyncIOHandler)
    @PingService([ArqIngestTaskService])
    @UseServiceLock(ArqIngestTaskService,lockType='reader')
    @UsePipe(DataClassToDictPipe(),before=False)
    @BaseHTTPRessource.HTTPRoute('/results/', methods=[HTTPMethod.GET])
    async def get_jobs_result(self, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.arqService.get_jobs_results()
        
    @UseHandler(AsyncIOHandler)    
    @PingService([ArqIngestTaskService])
    @UseServiceLock(ArqIngestTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/info/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_info(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.exists(job_id, raise_on_exist=False)
        info  = await self.arqService.info(job)
        return info

    @UseHandler(AsyncIOHandler)
    @PingService([ArqIngestTaskService])
    @UseServiceLock(ArqIngestTaskService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/result/{job_id}/', methods=[HTTPMethod.GET])
    async def get_job_result(self, job_id: str, request: Request,response:Response,autPermission:AuthPermission=Depends(get_auth_permission)):
        job = await self.arqService.exists(job_id, raise_on_exist=False)
        result = await self.arqService.get_result(job)
        return result

    @UseLimiter('5/hour')
    @Throttle(uniform=(100,300))
    @PingService([ArqIngestTaskService])
    @UseServiceLock(ArqIngestTaskService,lockType='reader')
    @UseHandler(CostHandler,AsyncIOHandler,FileHandler,RedisHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{job_id}/', methods=[HTTPMethod.DELETE],response_model=AbortedJobResponse)
    async def abort_job(self, job_id: str, request: Request,response:Response,cost:Annotated[FileCost,Depends(FileCost)],broker:Annotated[Broker,Depends(Broker)],force:bool = Depends(force_update_query),autPermission:AuthPermission=Depends(get_auth_permission)):
        job,status = await self.arqService.exists(job_id, raise_on_exist=False,return_status=True)

        match status:
            case JobStatus.queued | JobStatus.deferred:
                info = await self.arqService.info(job)
                await self.arqService.dequeue_task(job_id)

                if info.kwargs.get('_nickname',None) == ArqDataTaskConstant.FILE_DATA_TASK:
                    size,uri,sha = info.kwargs.get('size',0), info.kwargs.get('uri',None),info.kwargs.get('sha','unknown')
                    file_path = self.arqService.compute_data_file_upload_path(uri)
                    await RunInThreadPool(self.fileService.delete_file)(file_path)
                return AbortedJobResponse(aborted= True, metadata=[IngestDataUriMetadata(uri=uri,size=size,sha=sha)],status=status)
                
            case JobStatus.complete:
                return AbortedJobResponse(metadata=[],aborted=False,status=status)
            
            case JobStatus.in_progress:
                if not force:   
                    raise JobInProgressError(job_id)    
                    
                result = await self.arqService.abort(job)
                return AbortedJobResponse(metadata=[],aborted=bool(result),status=status)
            
            case _:
                raise UnexpectedJobStatusError(
                    job_id,
                    status
                )

@UseRoles([Role.ADMIN])
@PingService([ArqIngestTaskService])
@IncludeRessource(JobArqRessource)
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,CostHandler,DataIngestHandler)
@HTTPRessource('data-ingest')
class DataIngestRessource(BaseHTTPRessource):
    
    @staticmethod
    async def docling_guard(ingestTask:FileUploadDataIngestModel):
        configService = Get(ConfigService)
        if not configService.INSTALL_DOCLING and ingestTask.use_docling:
            return False,"Docling is not installed"
        return True,""

    @staticmethod
    async def crawl4ai_guard():
        configService = Get(ConfigService)
        if not configService.INSTALL_CRAWL4AI:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Crawl4ai is not installed"
            )
    
    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,fileService:FileService,arqService:ArqIngestTaskService,customService:CustomService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.fileService = fileService
        self.arqService = arqService
        self.customService = customService

    @UseLimiter('10/hour')
    @Throttle(normal=(300,150))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @PingService([RedisService,{'cls':LLMProviderService,'kwargs':VerifyLLMConfig()}])
    @UsePipe(QueryToModelPipe('ingestTask'),MerchantPipe)
    @UseServiceLock(RedisService,ArqIngestTaskService,LLMProviderService,lockType='reader')
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseHandler(UploadFileHandler,ArqHandler,AsyncIOHandler,PydanticHandler,AgenticHandler,RedisHandler)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.FILE_DATA_TASK),UploadFilesGuard(),docling_guard)
    @BaseHTTPRessource.HTTPRoute('/file/',methods=[HTTPMethod.POST],response_model=FileUploadIngestEnqueueResponse)
    async def ingest_files(self,ingestTask:Annotated[FileUploadDataIngestModel,Depends(lambda :None)], request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[FileIngestCost,Depends(FileIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],files:List[UploadFile]= File(...),request_id:str = Depends(get_request_id),query:FileDataIngestQuery = Depends(FileDataIngestQuery), autPermission:AuthPermission=Depends(get_auth_permission)):
        _response = FileUploadIngestEnqueueResponse()
        ingest_sha = set()
        for file in files:
            try:
                uri= file.filename.lower()
                file_path = self.arqService.compute_data_file_upload_path(uri)
                sha = await self.fileService.compute_sha256(file.file)

                if sha in ingest_sha:
                    raise JobAlreadyExistsError(uri,'File already added')
                
                ingest_sha.add(sha)

                await self.arqService.exists(uri, True,True)
                await self.arqService.search(ArqDataTaskConstant.FILE_DATA_TASK,{'sha':sha},True)
                await self.fileService.download_file(file_path, await file.read())

                meta = IngestDataUriMetadata(uri=uri, size=file.size,sha=sha)
                _response.metadata.append(meta)

                merchant.safe_payment(
                    None,
                    FileResponseUploadModel(metadata=[meta]),
                    self.arqService.enqueue_task,ArqDataTaskConstant.FILE_DATA_TASK,
                    job_id=uri,
                    expires=ingestTask.expires,
                    defer_by=ingestTask.defer_by,
                    kwargs={**ingestTask.model_dump(mode='json',exclude=('expires','defer_by')),
                            **meta.model_dump(),
                            'request_id':request_id,
                            '_nickname':ArqDataTaskConstant.FILE_DATA_TASK,
                            'state':None,
                            'step':None
                            }
                )
            except JobAlreadyExistsError as e:
                _response.errors[uri] = UploadError(reason=e.reason,file_path=file_path)
            except OSError as e:
                _response.errors[uri] = UploadError(reason = str(e),file_path=file_path)
        
        return _response

    @UseLimiter('5/hour')
    @UsePipe(MerchantPipe())
    @Throttle(normal=(700,1500))
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @PingService([RedisService,{'cls':LLMProviderService,'kwargs':VerifyLLMConfig(crawl=True)}])
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseServiceLock(RedisService,ArqIngestTaskService,CustomService,LLMProviderService,lockType='reader')
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.WEB_DATA_TASK),crawl4ai_guard)
    @UseHandler(ArqHandler,AsyncIOHandler,AgenticHandler,RedisHandler,MiniServiceHandler,VaultHandler)
    @BaseHTTPRessource.HTTPRoute('/web/',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def ingest_web_crawling(self,request:Request,response:Response,ingestTask:WebCrawlingDataIngestModel,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[WebIngestCost,Depends(WebIngestCost)],merchant:Annotated[Merchant,Depends(Merchant)],request_id:str = Depends(get_request_id),autPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Web crawl the web and extract meaningful information
        """
    
    @UseLimiter('5/hour')
    @UsePipe(MerchantPipe())
    @Throttle(normal=(300,150))
    @UsePermission(ProfilePermission)
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UsePipe(MiniServiceInjectorPipe(ProfileService))
    @UsePipe(update_status_upon_no_metadata_pipe,before=False)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseHandler(ArqHandler,AsyncIOHandler,MiniServiceHandler,VaultHandler,AgenticHandler,RedisHandler)
    @PingService([RedisService,{'cls':LLMProviderService,'kwargs':VerifyLLMConfig(vector=False)}])
    @UseServiceLock(RedisService,ArqIngestTaskService,ProfileService,LLMProviderService,lockType='reader',as_manager=True)
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.API_DATA_TASK),DataIngestDatabaseGuard(False))
    @BaseHTTPRessource.HTTPRoute('/api/{profile}/',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def ingest_api_data(self,profile:Annotated[ProfileMiniService,Depends(get_profile)],request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],merchant:Annotated[Merchant,Depends(Merchant)],cost:Annotated[WebIngestCost,Depends(WebIngestCost)],request_id:str = Depends(get_request_id),authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Accepts a JSON body describing an `APIFetchTask` and enqueues it.
        """

    @Throttle(normal=(300,150))
    @UsePipe(MerchantPipe())
    @HTTPStatusCode(status.HTTP_202_ACCEPTED)
    @UseHandler(ArqHandler,AsyncIOHandler,RedisHandler,AgenticHandler,RedisHandler)
    @UseInterceptor(DataCostInterceptor(CostConstant.DOCUMENT_CREDIT,'purchase'))
    @UseServiceLock(RedisService,ArqIngestTaskService,LLMProviderService,lockType='reader')
    @UseGuard(ArqDataTaskGuard(ArqDataTaskConstant.RESEARCH_DATA_TASK),crawl4ai_guard)
    @PingService([RedisService,{'cls':LLMProviderService,'kwargs':VerifyLLMConfig(research=True)}])
    @BaseHTTPRessource.HTTPRoute('/research/{profile}',methods=[HTTPMethod.POST],response_model=EnqueueResponse,mount=False)
    async def ingest_research(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],merchant:Annotated[Merchant,Depends(Merchant)],request_id:str = Depends(get_request_id),authPermission:AuthPermission=Depends(get_auth_permission)):
        """
        Engage a broad research by fetching url concept and crawling those pages
        """


    async def on_startup(self):
        self.arqService.register_task(DATA_TASK_REGISTRY_NAME)
        await self.arqService.initialize()
    
    async def on_shutdown(self):
        await self.arqService.close()

