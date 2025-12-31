from typing import List
from fastapi import BackgroundTasks, UploadFile
from app.classes.cost_definition import FileCostDefinition
from app.container import Get
from app.definition._cost import DataCost
from app.models.file_model import FileResponseUploadModel
from app.services import CostService


class FileCost(DataCost):

    PRE_NAME =  "File upload:"
    POST_NAME = "File processing:"

    
    def init(self, default_price, credit_key):
        super().init(default_price, credit_key)
        costService = Get(CostService)

        self.definition:FileCostDefinition = costService.costs_definition.get(credit_key,FileCostDefinition(max_file_size=10,max_file_size_extra_per_mb=1))


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

    
    def compute_cost(self,name, filename:str|None,size:float |None):
        max_file_size = self.definition.get('max_file_size', 10)
        cost_per_extra_mb = self.definition.get('max_file_size_extra_per_mb', 1)

        file_size_mb = (size or 0) / (1024 * 1024)
        filename = filename or "unknown"
        delta = max_file_size - file_size_mb

        if delta < 0:
            cost = int((delta*-1) * cost_per_extra_mb) + int(file_size_mb)
            description = f"{name} {filename} ({file_size_mb:.2f} MB, exceeds limit of {max_file_size} MB)"
        else:
            cost = int(file_size_mb)
            description = f"{name} {filename} ({file_size_mb:.2f} MB)"
        return cost,description
    