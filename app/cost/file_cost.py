from typing import List
from fastapi import BackgroundTasks, Depends, UploadFile
from app.classes.auth_permission import AuthPermission
from app.classes.cost_definition import FileCostDefinition
from app.container import Get
from app.definition._cost import DataCost
from app.depends.dependencies import get_auth_permission, get_request_id
from app.models.file_model import FileResponseUploadModel
from app.services import CostService
from app.services.file.file_service import FileService


class FileCost(DataCost):

    PRE_NAME =  "File upload:"
    POST_NAME = "File processing:"
    REFUND_NAME = "File refund:"

    DEFAULT_DEF = FileCostDefinition(max_file_size=10,max_file_size_extra_per_mb=1)

    def __init__(self,  request_id: str=Depends(get_request_id),authPermission:AuthPermission|None=Depends(get_auth_permission)):
        super().__init__(request_id, authPermission)
        self.costService = Get(CostService)
        self.fileService = Get(FileService)

    def init(self, default_price, credit_key):
        super().init(default_price, credit_key)
        self.definition:FileCostDefinition = self.costService.costs_definition.get(credit_key,FileCost.DEFAULT_DEF)
        self.max_file_size = self.definition.get('max_file_size')
        self.cost_per_extra_mb = self.definition.get('max_file_size_extra_per_mb')

    def pre_purchase(self, files: List[UploadFile]):
        """Compute cost for uploading files before they are processed.
        
        Iterates over each file, computes cost based on file size using FileCostDefinition,
        and adds purchase items.
        """
        for file in files:

            prices = self.compute_prices(self.PRE_NAME, file.filename,file.size)
            for d,c,q in prices:
                self.purchase(d,c,q) 

    def post_purchase(self, result: FileResponseUploadModel, backgroundTasks: BackgroundTasks):
        """Compute cost for files after they are processed.
        
        Iterates over result.meta tuples (filename, size), computes cost using FileCostDefinition,
        and adds purchase items.
        """
        for (metadata,task) in zip(result.metadata,backgroundTasks.tasks):
            
            filename,file_size_mb = metadata.uri,metadata.size
            prices = self.compute_prices(self.POST_NAME, filename,file_size_mb)
            for d,c,q in prices:
                self.purchase(d,c,q) 

    def post_refund(self, result:FileResponseUploadModel):
        for  metadata in result.metadata:

            filename,size = metadata.uri,metadata.size
            prices = self.compute_prices(self.REFUND_NAME,filename,size)
            for d,c,q in prices:
                self.refund(d,c,q)
 
    def compute_prices(self,name, filename:str|None,size:float |None):
        file_size_mb = self.fileService.file_size_converter(size,'mb')
        filename = filename or "unknown"
        delta = self.max_file_size - file_size_mb
        purchase:list[tuple[str,int]] = [] 

        if delta < 0:
            c = self.cost_per_extra_mb
            q = int(delta*-1)
            d = f"{name} {filename} ({file_size_mb:.2f} MB, exceeds limit of {self.max_file_size} MB)"
            purchase.append((d,c,q))

        q = int(file_size_mb)
        d = f"{name} {filename} ({file_size_mb:.2f} MB)"
        purchase.append((d,1,q))

        return purchase
    