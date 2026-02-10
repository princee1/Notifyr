from typing import List
from app.definition._service import DEFAULT_BUILD_STATE, BaseService, Service
from app.models.custom_model import CustomModel
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.utils.constant import MongooseDBConstant
from app.utils.validation import Validator


@Service()
class CustomModelService(BaseService):
    
    def __init__(self,configService:ConfigService,mongooseService:MongooseService):
        super().__init__()
        self.clear()  
        self.configService = configService
        self.mongooseService = mongooseService 

    def clear(self):
        self.edge_map = {}
        self.models = {}
        self.edges = {}
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        self.clear()
        models = self.mongooseService.sync_find(MongooseDBConstant.CUSTOM_MODEL_COLLECTION,CustomModel,return_model=True)
        self._create_models(models)
        self._build_edge_map()

    def verify_edge(self,model:CustomModel):
        ...
        
    def _create_models(self,models:List[CustomModel]):
        ...
    
    def _build_edge_map(self):
        ...


    
