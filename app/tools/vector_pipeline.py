from app.definition._tool import Pipeline
from app.models.agents_model import VectorPipelineModel
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.memcached_service import MemCachedService
from app.services.database.qdrant_service import QdrantService

class VectorRagPipeline(Pipeline):
	"""
	1. Embed the user query
	2. look up the cache if hit return response else
	3. look for those values in the vector database with, if it is not enough do another payload search
	4. compare and fetch with the top-k closet vector 
	5. do a tree depth search of related nodes only if needed
	6. filter content
	7. build the prompt with the user query
	8. prompt using the llm
	9. store the response in a cache or in the vector database
	"""

	def __init__(self,qdrantService:QdrantService,configService:ConfigService,customService:CustomService,memcachedService:MemCachedService,vectorModel:VectorPipelineModel):
			super().__init__()
			self.qdrantService = qdrantService
			self.configService = configService
			self.customService = customService
			self.memcachedService = memcachedService
			self.vectorConfig = vectorModel
	
	async def __call__(self,query:str):
			...

	async def search(self):
		...
	
	async def _search(self):
		...