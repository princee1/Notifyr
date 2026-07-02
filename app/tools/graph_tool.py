from dataclasses import dataclass
from typing import TypedDict
from app.classes.chunk import ChunkSource
from app.classes.nodes import KGraphFacts, SourceDescription
from app.definition._agent import BaseToolArtifact
from app.definition._tool import RetrievalTool, ToolContextFactory, ToolRuntime
from app.models.odm.tools_model import BroadRerankerSearchConfig, ContextCondition, KnowledgeGraphToolModel, MemoryToolModel
from app.services.config_service import ConfigService
from app.services.custom_service import CustomService
from app.services.database.graphiti_service import GraphitiService, GroupType,SearchResults,EntityNode,EpisodicNode,EntityEdge
from app.services.database.qdrant_service import QdrantService
from app.prompt import context_prompt, rag_prompt
from langchain.messages import ToolMessage

from app.utils.helper import slice_dict

@dataclass
class ContextSearchParam:
    query:str
    group:str
    
#NOTE  "Is this semantic knowledge?"

class Facts(TypedDict):
    target_uuid:str
    source_uuid:str
    sources:list[str]
    score:float

FACTS_KEYS = {'target_uuid','source_uuid','score'}

class RagKGArtifact(BaseToolArtifact):
    sources:list[ChunkSource]
    facts:list[Facts]
    domain:str
    group_type:str

class KnowledgeGraphTool(RetrievalTool):
    group_type:GroupType = 'domain' 
    
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService,config:KnowledgeGraphToolModel):
        super().__init__(config)
        self.graphitiService = graphitiService
        self.configService = configService
        self.config = config

    async def __call__(self,query:str,runtime:ToolRuntime):
        return await self.search(query,self.config.domain,runtime.tool_call_id)
        
    async def search(self,query:str,domain:str,tool_call_id)->SearchResults:
        try:
            async with ToolContextFactory(artifact={'domain':domain,'group_type':self.group_type}) as factory:
                async with self.graphitiService.lock('reader'):
                    contexts:list[KGraphFacts] = []
                    params = ContextSearchParam(query,domain)
                    self._force_non_broad_search()
                    results = await self._search_wrapper(query,domain,None)
                    await self.graph_search(results,set(),contexts,params,0)
                    if not self.reranker_config._skip:
                        contexts = sorted(contexts,key=lambda k:k['score'],reverse=True)[self.reranker_config.top_k:]
                    prompt_context = context_prompt.GRAPH_RAG_TEMPLATE(contexts)
                    artifact = self.to_artifact(contexts)
                    factory.update(artifact)
        except:
            ...
                
        return ToolMessage(
            prompt_context,
            tool_call_id=tool_call_id,
            status=factory.status,
            artifact=factory.as_artifact(),
            additional_kwargs={**factory.as_option(),**self.metadata}
        )
                
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
            kg_facts = KGraphFacts(target_uuid=f.target_node_uuid,
                                   source_uuid=f.source_node_uuid,
                                   fact=f.fact,
                                    target_summary=target_summary,
                                    source_summary=source_summary,
                                    score=score,source=sources)
            contexts.append(kg_facts)

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
            self.config.broad_search = BroadRerankerSearchConfig()
            self.config.broad_search._s = True
    
    def to_artifact(self,contexts:list[KGraphFacts])->RagKGArtifact:
        facts:list[Facts] = []
        sources:list[ChunkSource] = []

        source_seen = set()
        hashes = set()

        for c in contexts:
            f = slice_dict(c,FACTS_KEYS,mode='include',copy=True)
            source = []
            for s in c['source']:
                source.append(s.id)
                if s.id in source_seen:
                    continue
                source_seen.add(s.id)
                sources.append({'chunk_id':s.id,'document_id':s.document_id,'document_name':s.document_name,'source':s.source})

            f['sources'] = source
            facts.append(f)

        return {'sources':sources,'facts':facts,'hashes':hashes}

    @property
    def reranker_config(self)->BroadRerankerSearchConfig:
        return self.config.broad_search
    
    @classmethod
    def to_metadata(cls):
	    return super().to_metadata(f'Knowledge-Graph')

class MemoryTool(KnowledgeGraphTool):
    
    condition: ContextCondition = ContextCondition(auth=['registered'])
    group_type:GroupType = 'contact' 
    
    def __init__(self,graphitiService:GraphitiService,configService:ConfigService,config:MemoryToolModel):
        super().__init__(graphitiService,configService,config)

    async def __call__(self,query:str,runtime:ToolRuntime):
        contact_id = runtime.context.user_id
        tool_call_id = runtime.tool_call_id
        return await self.search(query,contact_id,tool_call_id)
    
    @classmethod
    def to_metadata(cls):
	    return super().to_metadata(f'Memory-KG')
