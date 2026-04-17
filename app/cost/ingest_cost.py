import math
import sys
from typing import List, Literal, Tuple
from fastapi import UploadFile
from app.classes.cost_definition import MarkdownCostDefinition
from app.classes.crawl import MarkdownDocumentSize
from app.container import Get
from app.cost.file_cost import FileCost
from app.definition._cost import Cost, DataCost
from app.models.file_model import FileResponseUploadModel
from app.models.ingest_model import DeleteIngestUriMetadata, FileUploadDataIngestModel, WebCrawlingDataIngestModel, WebCrawlingUriMetadata
from app.services.file.file_service import FileService


class FileIngestCost(FileCost):

    INGEST_PRENAME = FileCost.PRE_NAME('document')
    INGEST_POSTNAME = FileCost.POST_NAME('document')
    INGEST_REFUND = FileCost.REFUND_NAME('document')

    def pre_purchase(self, files: List[UploadFile],ingestTask:FileUploadDataIngestModel):
        for file in files:
            prices = []
            if ingestTask.vector_config:
                prices.extend(self.compute_prices(f'[Vector] - {self.INGEST_PRENAME}', file.filename,file.size))
            
            if ingestTask.graph_config:
                prices.extend(self.compute_prices(f'[K-Graph] - {self.INGEST_PRENAME}', file.filename,file.size))

            for d,c,q in prices:
                self.purchase(d,c,q) 

    def post_purchase(self, result: FileResponseUploadModel,ingestTask:FileUploadDataIngestModel):
        for i,metadata in enumerate(result.metadata):
            
            filename,file_size_mb = metadata.uri,metadata.size
            prices = []
            if ingestTask.vector_config:
                prices.extend(self.compute_prices(f'[Vector] - {self.INGEST_POSTNAME}', filename,file_size_mb))
                
            if ingestTask.graph_config:
                prices.extend(self.compute_prices(f'[K-Graph] - {self.INGEST_POSTNAME}', filename,file_size_mb))

            for d,c,q in prices:
                self.purchase(d,c,q) 

    def post_refund(self, result:FileResponseUploadModel,db_config:Tuple[bool,bool]):
        for  metadata in result.metadata:

            filename,file_size_mb = metadata.uri,metadata.size
            prices = []
            if db_config[0]: # vector
                prices.extend(self.compute_prices(f'[Vector] - {self.INGEST_REFUND}', filename,file_size_mb))
                
            if db_config[1]: # graph
                prices.extend(self.compute_prices(f'[K-Graph] - {self.INGEST_REFUND}', filename,file_size_mb))

            for d,c,q in prices:
                self.refund(d,c,q)


#########################################################################################################
####################               MarkdownCostDefinition          ######################################
#########################################################################################################

RefundDetail = Literal['full','partial']

class MarkdownResultIngestCost(DataCost):

    DEFAULT_DEF = MarkdownCostDefinition(max_html_mb=2,max_pdf_mb=10)

    def init(self, default_price, credit_key,definition_name:str,refund_detail:RefundDetail ='partial',crawl_type:Literal['Crawl','Research']='Crawl'):
        super().init(default_price, credit_key)
        self.definition_name = definition_name
        self.crawl_type = crawl_type
        self.refund_detail = refund_detail
        self.fileService = Get(FileService)
        self.definition:MarkdownCostDefinition = self.costService.fetch_definition(self.crawl_type.lower(),self.DEFAULT_DEF)
        self.max_html_kb = self.fileService.bytes_conversion(self.definition['max_html_mb'],'mb','kb')
        self.max_pdf_kb = self.fileService.bytes_conversion(self.definition['max_pdf_mb'],'mb','kb')
        return self

    def post_refund(self, results:List[MarkdownDocumentSize],db_config:Tuple[bool,bool],url_size:int,pdf_size:int):
        url_cptr = 0
        pdf_cptr = 0

        total_cost = 0

        for document in results:
            if document['doc_type'] == 'pdf':
                pdf_cptr+=1
                cost_size = self.max_html_kb - document['size']
            else:
                url_cptr+=1
                cost_size = self.max_html_kb - document['size']

            if self.refund_detail == 'full':
                total_cost += cost_size
            else:
                if db_config[0]:
                    self.refund(f'{self.crawl_type} [Vector] Credit Refund: {document["description"]}',1,cost_size)
                
                if db_config[1]:
                    self.refund(f'{self.crawl_type} [Graph] Credit Refund: {document["description"]}',1,cost_size)
                    
        if self.refund_detail == 'full':
            if db_config[0]:
                self.refund(f'{self.crawl_type} [Vector] Credit Refund',total_cost,1)

            if db_config[1]:
                self.refund(f'{self.crawl_type} [Graph] Credit Refund',total_cost,1)

        diff_url = url_size - url_cptr
        diff_pdf = pdf_size - pdf_cptr

        if diff_url >0:
            if db_config[0]:
                self.refund(f'{self.crawl_type} [Vector] HTML Top Up Refund',self.max_html_kb,diff_url)

            if db_config[1]:
                self.refund(f'{self.crawl_type} [Graph] HTML Top Up Refund',self.max_html_kb,diff_url)
        
        if diff_pdf > 0:
            if db_config[0]:
                self.refund(f'{self.crawl_type} [Vector] PDF Top Up Refund',self.max_pdf_kb,diff_pdf)

            if db_config[1]:
                self.refund(f'{self.crawl_type} [Graph] PDF Top Up Refund',self.max_pdf_kb,diff_pdf)
    
#########################################################################################################
####################               CrawlMarkdown CostDefinition         #################################
#########################################################################################################

class CrawlMarkdownIngestCost(MarkdownResultIngestCost):
    
    def init(self, default_price, credit_key,refund_mode:RefundDetail ='partial'):
        return super().init(default_price, credit_key,'Crawl Ingestion',refund_mode,'Crawl')
    
    def pre_purchase(self, ingestTask:WebCrawlingDataIngestModel)->int:
        ingestTask.compute_size()
        self.compute(ingestTask)
        
    def post_purchase(self,ingestTask:WebCrawlingDataIngestModel):
        self.compute(ingestTask)

    def post_refund(self,metadata: WebCrawlingUriMetadata,db_config:Tuple[bool,bool]):
        if self.refund_detail == 'full':
            if db_config[0]:
                self.refund(f'[Crawl Refund Vector]', metadata.size, 1)

            if db_config[1]:
                self.refund(f'[Crawl Refund Vector]', metadata.size, 1)
        else:
            if db_config[0]:
                self.refund(f'[Crawl Refund Vector] - website url', self.max_html_kb,metadata.url_size)
                self.refund(f'[Crawl Refund Vector] - pdf url', self.max_pdf_kb,metadata.pdf_size)

            if db_config[1]:
                self.refund(f'[Crawl Refund K-Graph] - website url', self.max_html_kb,metadata.url_size)
                self.refund(f'[Crawl Refund K-Graph] - pdf url', self.max_pdf_kb,metadata.pdf_size)

    def compute(self,ingestTask:WebCrawlingDataIngestModel):
        if ingestTask.vector_config:
            self.purchase(f'[Vector] - {ingestTask._description}',self.max_html_kb,ingestTask._url_size)

        if ingestTask.graph_config:
            self.purchase(f'[K-Graph] - {ingestTask._description}',self.max_html_kb,ingestTask._url_size)
        
        if ingestTask.vector_config:
            self.purchase(f'[Vector] - pdf',self.max_pdf_kb,ingestTask.pdf_size)

        if ingestTask.graph_config:
            self.purchase(f'[K-Graph] - pdf',self.max_pdf_kb,ingestTask.pdf_size)
    
    def total_size(self,url:int,pdf:int):
        return (url * self.max_html_kb + pdf * self.max_pdf_kb)

    @property
    def total_max_kb(self):
        return self.max_html_kb + self.max_pdf_kb


#########################################################################################################
####################               ResearchMarkdown CostDefinition         ##############################
#########################################################################################################

class ResearchMarkdownIngestCost(CrawlMarkdownIngestCost):
    
    def init(self, default_price, credit_key,refund_mode:RefundDetail ='partial'):
        return super().init(default_price, credit_key,'Research Ingestion',refund_mode,'Research')

    
#########################################################################################################
####################               DeleteDocument CostDefinition         ##############################
#########################################################################################################


class DeleteDocumentIngestCost(DataCost):
    
    def change_definition_name(self,name:str):
        self.definition_name = name
    
    def change_db_config(self,db_config:Tuple[bool,bool]):
        self.db_config = db_config

    def post_refund(self, results:List[DeleteIngestUriMetadata]):
        for result in results:
            match result.task:
                case 'api':
                    ...
                
                case 'crawl':
                    cost = CrawlMarkdownIngestCost(self.request_id,self.issuer)
                    cost.init(1,self.credit_key,'full')
                    
                case 'file':
                    cost = FileIngestCost(self.request_id,self.issuer)
                    cost.init(1,self.credit_key)
                    result = FileResponseUploadModel(metadata=[result])
                
                case 'research':
                    cost = ResearchMarkdownIngestCost(self.request_id,self.issuer)
                    cost.init(1,self.credit_key,'full')
                
                case _:
                    ...

            cost.post_refund(result,self.db_config)
            self += cost
            