from app.classes.chunk import ChunkContext
from app.classes.embeddings import EmbeddingWrapper
from app.classes.qdrant import QdrantCollectionDoesNotExistError
from app.definition._tool import ContextPipelineTool
from app.models.tools_model import VectorToolModel
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.qdrant_service import QdrantService
from app.prompt import tools_prompt

class GraphChunkContext(ChunkContext):
	computed_similarity:float

class VectorRagTool(ContextPipelineTool):

	def __init__(self,qdrantService:QdrantService,configService:ConfigService,customService:CustomService,config:VectorToolModel):
			super().__init__(config)
			self.qdrantService = qdrantService
			self.configService = configService
			self.customService = customService
			self.config = config
			self.filter = self.qdrantService.to_filter(self.config.filter)
	
	async def __call__(self,query:str)->str:
		try:
			vector = await self.qdrantService.embed_query(query)
			with_vector = (self.sparse_config != None)
			config = self.config.model_dump(exclude=('filter',))
			contexts = await self.qdrantService.search(vector,filter=self.filter,with_vector=with_vector,**config)
			if self.sparse_config != None:
				results:list[GraphChunkContext] = []
				await self.graph_search(contexts,0,set(),results)
				contexts = sorted(results,key =lambda c:c.get('computed_similarity',0), reverse=True) #rerank

			prompt_context = tools_prompt.CHUNK_CONTEXT_TEMPLATE(contexts)
			return prompt_context
		except QdrantCollectionDoesNotExistError as e:
			return ''
	
	async def graph_search(self,contexts:list[ChunkContext],depth:int,seen:set[str]=None,results:list[GraphChunkContext]=None):
		if depth >= self.sparse_config.max_depth:
			return
		
		for ctx in contexts:
			if ctx['chunk_id'] in seen:
				continue
			seen.add(ctx['chunk_id'])

			if not ctx['relationship']:
				continue
			similar_context:list[tuple[str,int]] = []
			rel_points:dict[str,ChunkContext] = await self.qdrantService.get_points(self.collection,ctx['relationship'],True,5,'dict')
			base_vector = EmbeddingWrapper(ctx['chunk_id'],ctx['vector'],None)
			for i,(chunk_id,_ctx) in enumerate(rel_points.items()):
				if chunk_id in seen:
					continue
				dist = EmbeddingWrapper.cosine(base_vector,EmbeddingWrapper(chunk_id,_ctx['vector'],None))
				_ctx['similarity'] = dist
				if dist < self.sparse_config.thresh_add:
					seen.add(chunk_id)
					continue
				if dist < self.sparse_config.thresh_search:
					seen.add(chunk_id)
					self.compute_similarity(_ctx,ctx,depth)
					if len(results) >= self.sparse_config.max_context:
						return
				else:
					similar_context.append((chunk_id,dist))

			sorted_contexts = sorted(similar_context,reverse=True,key=lambda c:c[1])[self.sparse_config.branching_factor:]
			await self.graph_search(sorted_contexts,depth+1,seen=seen,results=results)
		
		return

	def compute_similarity(self,child:GraphChunkContext,parent:GraphChunkContext,depth:int):
		factor = parent.get('computed_similarity',1)
		sim = child['similarity']/(depth+1)
		child['computed_similarity'] = factor * sim
		
	@property
	def collection(self):
		return	self.config.collection

	@property
	def sparse_config(self):
		return self.config.disperse_search