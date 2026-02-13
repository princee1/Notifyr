from typing import Dict, List, Tuple

from pydantic import BaseModel
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.models.custom_model import CustomModel
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.utils.constant import MongooseDBConstant
from app.utils.model_creation import MODEL_REGISTRY, cerberus_schema_to_pydantic
from app.utils.validation import Validator


@Service()
class CustomService(BaseService):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService 
        self._initialize()  
   
    def build(self, build_state = DEFAULT_BUILD_STATE):
        self._initialize()
        models = self.mongooseService.sync_find(MongooseDBConstant.CUSTOM_MODEL_COLLECTION,CustomModel,return_model=True)
        self._create_models(models)

    def _initialize(self):
        self.models_registry:Dict[str,BaseModel] = {}
        self.models:Dict[str,CustomModel] = {}

    def _create_models(self,models:List[CustomModel]):

        for m in models:
            try:
                cerberus_schema_to_pydantic(m.schema,m.alias)
                self.models[m.alias] = m 
            except:
                continue
        
        self.models_registry = MODEL_REGISTRY

    def to_entities(self,entities:List[str]):
        entities_map = {}
        for e in entities:
            if e not in self.models_registry:
                continue

            if e not in self.models:
                continue

            if self.models[e].model_type != 'Entity':
                continue

            entities_map[e] = self.models_registry[e]
        
        return entities_map
        
    def to_edge(self,edges:List[str]):
        edge = {}
        for e in edges:
            if e not in self.models_registry:
                continue

            if e not in self.models:
                continue

            if self.models[e].model_type != 'Edge':
                continue

            edge[e] = self.models_registry[e]
        
        return edge
    
    def to_edge_map(self,edges:List[str],entities:list[str]):
        temp_e = set(entities)
        edge_map:Dict[tuple[str,str],list[str]] = {}
        for e in edges:
            if e not in self.models:
                continue
            m = self.models[e]
            if m.model_type != 'Edge':
                continue

            for edges in m.edge_map:
                edge1,edge2 = edges
                if edge1 not in self.models:
                    break
                if edge2 not in self.models:
                    break

                if edge1 not in temp_e:
                    break

                if edge2 not in temp_e:
                    break

                edges_key = (edge1,edge2)
                edges_key_2 = (edge2,edge1)

                if edges_key not in edge_map and edges_key_2 not in edge_map:
                    edge_map[edges_key] = [e]
                else:
                    edge_map[edges_key].append(e)
        return edge_map

    def verify_edge(self, model: CustomModel):
        for (e1, e2) in model.edge_map:

            if e1 not in self.models:
                raise ValueError(f"Edge endpoint '{e1}' not found in models.")

            if e2 not in self.models:
                raise ValueError(f"Edge endpoint '{e2}' not found in models.")

            if self.models[e1].model_type != 'Entity':
                raise ValueError(f"Model '{e1}' is not of type 'Entity'.")

            if self.models[e2].model_type != 'Entity':
                raise ValueError(f"Model '{e2}' is not of type 'Entity'.")
    


    
