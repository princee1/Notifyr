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

    def __init__(self,  request_id: str=Depends(get_request_id),authPermission:AuthPermission=Depends(get_auth_permission)):
        super().__init__(request_id, authPermission)
        self.costService = Get(CostService)
        self.fileService = Get(FileService)

    def init(self, default_price, credit_key):
        super().init(default_price, credit_key)
        self.definition:FileCostDefinition = self.costService.costs_definition.get(credit_key,FileCost.DEFAULT_DEF)

    def pre_purchase(self, files: List[UploadFile]):
        """Compute cost for uploading files before they are processed.
        
        Iterates over each file, computes cost based on file size using FileCostDefinition,
        and adds purchase items.
        """
        for file in files:
            cost, description = self.compute_cost(self.PRE_NAME, file.filename,file.size)

            self.purchase(description, cost)

    def post_purchase(self, result: FileResponseUploadModel, backgroundTasks: BackgroundTasks):
        """Compute cost for files after they are processed.
        
        Iterates over result.meta tuples (filename, size), computes cost using FileCostDefinition,
        and adds purchase items.
        """
        for (filename, file_size_mb),task in zip(result.meta,backgroundTasks):
            cost, description = self.compute_cost(self.POST_NAME, filename,file_size_mb)

            self.purchase(description, cost) 

    def post_refund(self, result:FileResponseUploadModel):
        for filename,size in result.meta:
            cost,description = self.compute_cost(self.REFUND_NAME,filename,size)

            self.refund(description,cost)
 
    def compute_cost(self,name, filename:str|None,size:float |None):
        max_file_size = self.definition.get('max_file_size', 10)
        cost_per_extra_mb = self.definition.get('max_file_size_extra_per_mb', 1)

        file_size_mb = self.fileService.file_size_converter(size,'mb')
        filename = filename or "unknown"
        delta = max_file_size - file_size_mb

        if delta < 0:
            cost = int((delta*-1) * cost_per_extra_mb) + int(file_size_mb)
            description = f"{name} {filename} ({file_size_mb:.2f} MB, exceeds limit of {max_file_size} MB)"
        else:
            cost = int(file_size_mb)
            description = f"{name} {filename} ({file_size_mb:.2f} MB)"
        return cost,description
    