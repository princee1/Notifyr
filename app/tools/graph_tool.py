from dataclasses import dataclass
from app.classes.nodes import KGraphFacts, SourceDescription
from app.definition._tool import ContextPipelineTool
from app.models.tools_model import BroadRerankerSearchConfig, KnowledgeGraphToolModel, MemoryToolModel
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.graphiti_service import GraphitiService, GroupType,SearchResults,EntityNode,EpisodicNode,EntityEdge
from app.services.database.qdrant_service import QdrantService
from app.prompt import tools_prompt

@dataclass
class ContextSearchParam:
    query:str
    group:str
    
class KnowledgeGraphTool(ContextPipelineTool):
    group_type:GroupType = 'domain' 
    
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService,config:KnowledgeGraphToolModel):
        super().__init__(config)
        self.graphitiService = graphitiService
        self.configService = configService
        self.config = config

    async def __call__(self,query:str):
        return await self.search(query,self.config.domain)
        
    async def search(self,query:str,group:str)->SearchResults:
        async with self.graphitiService.statusLock.reader:
            contexts:list[KGraphFacts] = []
            params = ContextSearchParam(query,group)
            self._force_non_broad_search()
            results = await self._search_wrapper(query,group,None)
            await self.graph_search(results,set(),contexts,params,0)
            if not self.reranker_config._skip:
                contexts = sorted(contexts,key=lambda k:k['score'],reverse=True)[self.reranker_config.top_k:]
            contexts = tools_prompt.GRAPH_CONTEXT_TEMPLATE(contexts)
            return contexts
    
    async def graph_search(self,result:SearchResults,seen:set[str],contexts:list[KGraphFacts],params:ContextSearchParam,depth:int):
        _episodes:dict[str,EpisodicNode] = {}
        _entities:dict[str,EntityNode] = {}
        _temp_entities:list[tuple[EntityEdge,float]] = []

        for ep in result.episodes:
            _episodes[ep.uuid] = _episodes
        
        for e,s in zip(result.nodes,result.node_reranker_scores):
            _entities[e.uuid] = e
            if self.reranker_config._skip:
                continue
            if s<self.reranker_config.thresh_search or e.uuid in seen:
                continue
            _temp_entities.append((e,s))    
            seen.add(e.uuid)
        
        facts = sorted(zip(result.edges,result.edge_reranker_scores),reverse=True,key=lambda k:k[1])
        for i,(f,s) in enumerate(filter(lambda fs: fs[1]>self.config.score_threshold,facts),start=1):
            if i == self.config.top_k:
                break
            if f.uuid in seen:
                continue
            seen.add(f.uuid)
            sources = []
            for ep in f.episodes:
                ep = _episodes[ep]
                sources.append(SourceDescription.From(ep.source_description))
            target_summary = _entities[f.target_node_uuid].summary if self.config.include_entity_summary else None
            source_summary = _entities[f.source_node_uuid].summary if self.config.include_entity_summary else None
            score = s # TODO compute score
            contexts.append(KGraphFacts(target_summary=target_summary,source_summary=source_summary,score=score,source=sources))

            if self.reranker_config._skip or len(contexts) >= self.reranker_config.max_context:
                return

        if self.reranker_config._skip or depth >= self.reranker_config.max_depth:
            return

        entities = sorted(_temp_entities,reverse=True,key=lambda k:k[1])[self.reranker_config.branching_factor:]
        for e,s in entities:                
            _r = await self._search_wrapper(params.query,params.group,e.uuid)
            await self.graph_search(_r,seen,contexts,params,depth+1)
        
    async def _search_wrapper(self,query:str,group:str,center_node=None):
        return await self.graphitiService.search(query,self.group_type,[group],center_node,edges=self.config.edges,entities=self.config.entities,)

    def _force_non_broad_search(self):
        if self.reranker_config == None:
            self.reranker_config = BroadRerankerSearchConfig()
            self.reranker_config._skip = True
    
    @property
    def reranker_config(self)->BroadRerankerSearchConfig:
        return self.reranker_config
        
class MemoryTool(KnowledgeGraphTool):
    
    group_type:GroupType = 'contact' 
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService,customService:CustomService,qdrantService:QdrantService,config:MemoryToolModel):
        super().__init__(graphitiService,configService,customService,qdrantService,config)

    async def __call__(self,query:str,contact_id:str):
        await self.search(query,contact_id)