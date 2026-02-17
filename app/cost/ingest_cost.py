from typing import List
from fastapi import UploadFile
from app.cost.file_cost import FileCost
from app.definition._cost import DataCost
from app.models.file_model import FileResponseUploadModel
from app.models.ingest_model import DataIngestFileModel


class IngestFileCost(FileCost):

    def pre_purchase(self, files: List[UploadFile],ingestTask:DataIngestFileModel):
            for file in files:
                prices = []
                if ingestTask.vector_config:
                    prices.extend(self.compute_prices(f'[Vector] - {self.PRE_NAME}', file.filename,file.size))
                
                if ingestTask.graph_config:
                    prices.extend(self.compute_prices(f'[K-Graph] - {self.PRE_NAME}', file.filename,file.size))

                for d,c,q in prices:
                    self.purchase(d,c,q) 

    def post_purchase(self, result: FileResponseUploadModel,ingestTask:DataIngestFileModel):
        for i,metadata in enumerate(result.metadata):
            
            filename,file_size_mb = metadata.uri,metadata.size
            prices = []
            if ingestTask.vector_config:
                prices.extend(self.compute_prices(f'[Vector] - {self.POST_NAME}', filename,file_size_mb))
                
            if ingestTask.graph_config:
                prices.extend(self.compute_prices(f'[K-Graph] - {self.POST_NAME}', filename,file_size_mb))

            for d,c,q in prices:
                self.purchase(d,c,q) 

class IngestWebCost(DataCost):
    ...
