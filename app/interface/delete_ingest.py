from typing import Dict, List, Literal, Tuple, get_args
from app.definition._interface import Interface, IsInterface
from app.errors.ingest_error import ConfigDatabase, Database
from app.models.ingest_model import DeleteIngestUriMetadata
from app.services.worker.arq_service import ArqIngestTaskService, JobStatusNotValidError,JobStatus
from app.errors.ingest_error import IngestConfigNotPresentError, SizeIngestNotFoundError, TaskIngestNameNotValidError
from app.utils.constant import ArqDataTaskConstant

Section = Literal['collection_name','domain']

@IsInterface
class DeleteIngestDocumentInterface(Interface):

    def __init__(self,arqService:ArqIngestTaskService):
        super().__init__()
        self.arqService = arqService
    
    async def delete_single_document(self,job_id:str,config:ConfigDatabase,database:Database,section:Section)->Tuple[DeleteIngestUriMetadata,str]:
        job,state = await self.arqService.exists(job_id,return_status=True)

        if state != JobStatus.complete:
            raise JobStatusNotValidError(job_id,state)
        
        info = await self.arqService.info(job)
        graph_config:dict = info.kwargs.get(config,None)

        if not graph_config:
            raise IngestConfigNotPresentError(config,database)
        
        task = info.kwargs('_nickname','unknown')

        if task not in get_args(ArqDataTaskConstant._DATA_TASK_TYPE):
            raise TaskIngestNameNotValidError(task,database)
        
        uri = info.kwargs['uri']
        
        if 'size' not in info.kwargs:
            raise SizeIngestNotFoundError(task,uri,database)

        meta = DeleteIngestUriMetadata(uri = uri,size = info.kwargs.get('size',0), task=task)

        domain = info.kwargs.get(section,None)

        return meta,domain
    
    async def delete_section(self,config:ConfigDatabase,section:Section,section_val:str)->Tuple[List[DeleteIngestUriMetadata],List[str],List[str],Dict]:
        jobs_queue = []
        jobs_done = []
        meta = []
        error= {}

        for info in [*await self.arqService.get_queued_jobs(),*await self.arqService.get_jobs_results()]:
            if info.kwargs.get(config,None) != None and info.kwargs.get(config,{}).get(section,None) == section_val:

                uri = info.kwargs.get('uri',None)

                task = info.kwargs('_nickname','unknown')

                if task not in get_args(ArqDataTaskConstant._DATA_TASK_TYPE):
                    error[uri] = DeleteIngestUriMetadata(uri=uri,size='unknown',task='unknown')
                    continue
                
                if 'size' not in info.kwargs:
                    error[uri] = DeleteIngestUriMetadata(uri,'unknown',task)
                    continue
    
                size = info.kwargs.get('size',0)

                if not hasattr(info,'result'):
                    jobs_queue.append(info.job_id)
                jobs_done.append(info.job_id)

                meta.append(DeleteIngestUriMetadata(uri,size,task))
        
        return meta,jobs_done,jobs_queue,error