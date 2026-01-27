from typing import Any, Iterator
from app.definition._service import BaseService, Service
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.mongoose_service import MongooseService
from app.services.vault_service import VaultService
from neo4j import AsyncNeo4jDriver, Neo4jDriver
import graphiti_core

@Service()
class Neo4JService(BaseService):
    
    def __init__(self,configService:ConfigService,vaultService:VaultService,mongooseService:MongooseService):
        super().__init__()
        self.vaultService = vaultService
        self.configService = configService
        self.mongooseService = mongooseService
    
    def build(self, build_state = ...):
        return
        try:
            self.client = AsyncNeo4jDriver(self.uri)
            client = Neo4jDriver(self.uri)
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
    
    async def add_episode(self):
        ...

    async def add_message(self):
        ...
    
    async def bulk_add_episode(self, iterator:Iterator[Any]):
        ...
    
    async def init_database(self,):
        ...

    
    

    @property
    def uri(self):
        return f'bolt://{self.configService.NEO4J_HOST}:7687'
    
