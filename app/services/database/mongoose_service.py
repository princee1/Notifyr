from typing import List
from pymongo.errors import ConnectionFailure,ConfigurationError, ServerSelectionTimeoutError
from pymongo import MongoClient
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service
from app.errors.service_error import BuildFailureError
from app.models.communication_model import *
from app.errors.db_error import *
from beanie import Document, PydanticObjectId, init_beanie
from app.services.config_service import ConfigService
from app.services.database.base_db_service import TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.secret_service import HCVaultService
from app.utils.constant import VaultTTLSyncConstant
from motor.motor_asyncio import AsyncIOMotorClient



D = TypeVar('D',bound=Document)

@Service(links=[LinkDep(HCVaultService,to_build=True,to_destroy=True)])     
class MongooseService(TempCredentialsDatabaseService):
    COLLECTION_REF = Literal["agent", "chat", "profile"]
    DATABASE_NAME = MongooseDBConstant.DATABASE_NAME

    def __init__(
        self,
        configService: ConfigService,
        fileService: FileService,
        vaultService: HCVaultService,
    ):
        super().__init__(configService, fileService,vaultService,VaultTTLSyncConstant.MONGODB_AUTH_TTL)

        self.client: AsyncIOMotorClient | None = None
        self._documents = []
        self.mongoConstant = MongooseDBConstant()

    ##################################################
    # CRUD-like API (Beanie style)
    ##################################################
    async def insert(self,model:Document,*args,**kwargs):
        return await model.insert(*args, **kwargs)

    async def get(self,model:Type[D],id:str,raise_:bool = True)->D:
        m = await model.get(PydanticObjectId(id))
        if m == None and raise_:
            raise DocumentDoesNotExistsError(id)
        return m
    
    async def find_all(self,model:Type[D])->List[D]:
        return await model.find_all().to_list()

    async def find(self, model: Type[D], *args, **kwargs):
        return await model.find(*args, **kwargs).to_list()

    async def find_one(self, model: Type[D], *args, **kwargs):
        return await model.find_one(*args, **kwargs)

    async def delete(self, model: D):
        return await model.delete()

    async def delete_all(self,model:Type[D],*args,**kwargs):
        return await model.delete_all(*args,**kwargs)

    async def count(self, model: Type[D], *args, **kwargs):
        return await model.find(*args, **kwargs).count()
    
    async def primary_key_constraint(self,model:D,raise_when:bool = None):
        pk_field = getattr(model,'_primary_key',None)
        if not pk_field:
            return
        
        pk_value = getattr(model,pk_field,None)
        if pk_value == None:
            return
        
        params = {pk_field:pk_value}
        is_exist= (await self.find_one(model.__class__,params) != None)
        if raise_when != None:
            if (raise_when and is_exist) or (not raise_when and not is_exist):
                raise DocumentPrimaryKeyConflictError(pk_value=pk_value,model=model.__class__,pk_field=pk_field)
        else:
            return is_exist

    async def exists_unique(self,model:D,raise_when:bool = None):
        unique_indexes = getattr(model,'unique_indexes',None)
        if unique_indexes == None:
            return False
        
        params = {i:getattr(model,i,None)  for i in unique_indexes }
        is_exist= (await self.find_one(model.__class__,params) != None)
        if raise_when != None:
            if (raise_when and is_exist) or (not raise_when and not is_exist):
                raise DocumentExistsUniqueConstraintError(exists=is_exist,model=model.__class__,params=params)
        else:
            return is_exist

    def sync_find(self,collection:str,model:Type[D],filter={},projection:dict={},return_model=False)->list[D]:
        
        filter['_class_id'] = {"$regex": f"{model.__name__}$" }
    
        if collection not in self.mongoConstant.available_collection:
            raise MongoCollectionDoesNotExists(collection)

        mongo_collection = self.sync_db[collection]
        docs= mongo_collection.find(filter,projection).to_list()
        return docs if not return_model else [model.model_construct(**doc) for doc in docs]
       
    ##################################################
    # Service lifecycle
    ##################################################

    def build(self, build_state=DEFAULT_BUILD_STATE):
        try:
            self.db_connection()
            super().build()
        except ConnectionFailure as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB connection error: {e}")

        except ConfigurationError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB configuration error: {e}")

        except ServerSelectionTimeoutError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB server selection timeout: {e}")

        except Exception as e:
            print(e)
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"Unexpected error: {e}")

    def db_connection(self):
        # fetch fresh creds from Vault
        self.creds = self.vaultService.database_engine.generate_credentials(VaultConstant.MONGO_ROLE)
        
        self.sync_client = MongoClient(self.mongo_uri)
        self.sync_db = self.sync_client[self.DATABASE_NAME]

        self.client = AsyncIOMotorClient(self.mongo_uri)
        self.motor_db = self.client[self.DATABASE_NAME]

    async def _creds_rotator(self):
        self.close_connection()
        self.db_connection()
        await self.init_connection()

    def close_connection(self):
        try:
            self.client.close()
            self.sync_client.close()
        except Exception as e:
            ...

    async def init_connection(self,):
        await init_beanie(
                database=self.motor_db,
                document_models=self._documents,
            )
        
    def register_document(self,*documents):
        temp = set()
        temp.update(self._documents)
        temp.update(list(documents))
        self._documents = list(temp)


    ##################################################
    # Connection string
    ##################################################
    @property
    def mongo_uri(self):
        return f"mongodb://{self.db_user}:{self.db_password}@{self.configService.MONGO_HOST}:27017/{self.DATABASE_NAME}"
        
    ##################################################
    # Healthcheck
    ##################################################
    
    def destroy(self, destroy_state = ...):
        self.close_connection()
    