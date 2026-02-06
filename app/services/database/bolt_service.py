from typing import Any, Iterator
from app.definition._service import BaseService, Service
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService, UvicornWorkerService
from app.services.database.mongoose_service import MongooseService
from app.services.vault_service import VaultService
from neo4j import AsyncGraphDatabase,GraphDatabase
import graphiti_core
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF

@Service()
class BoltService(BaseService):
    
    def __init__(self,uvicornWorkerService:UvicornWorkerService,configService:ConfigService,vaultService:VaultService,mongooseService:MongooseService):
        super().__init__()
        self.uvicornWorkerService = uvicornWorkerService
        self.vaultService = vaultService
        self.configService = configService
        self.mongooseService = mongooseService
    
    def build(self, build_state = ...):
        try:
            self.client = AsyncGraphDatabase().driver(self.uri,auth=('auth','password'))

            client = GraphDatabase.driver(self.uri,auth=('auth','password'),user_agent=self.uvicornWorkerService.INSTANCE_ID)
            client.verify_connectivity()
            client.verify_authentication()
        except:
            raise BuildFailureError()
        finally:
            client.close()

    async def close(self):
        ...

    async def search(self):
        ...
    
    async def center_search(self):
        ...

    async def add_episode(self):
        ...

    async def add_message(self):
        ...
    
    async def bulk_add_episode(self, iterator:Iterator[Any],episode_type:EpisodeType):
        ...
    
    async def init_database(self,):
        ...

    @property
    def uri(self):
        return f'bolt://{self.configService.BOLT_HOST}:7687'
    
