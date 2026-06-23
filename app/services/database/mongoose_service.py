import asyncio
from contextlib import asynccontextmanager
from typing import List, Literal, Type, TypeVar, Union
from pymongo.errors import ConnectionFailure,ConfigurationError, PyMongoError, ServerSelectionTimeoutError
from pymongo import MongoClient
from app.classes.mongo import BaseDocument, MongoCondition, simple_number_validation, validate_filter
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service, ServiceLockType
from app.errors.service_error import BuildFailureError
from app.errors.db_error import *
from beanie import Document, PydanticObjectId, init_beanie
from app.services.config_service import ConfigService
from app.services.database.base_db_service import CredentialName, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import AgenticConstant, MongooseDBConstant, VaultConstant, VaultTTLSyncConstant
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, OperationFailure

from app.utils.helper import subset_model

AGENTIC_CREDS='agentic'

D = TypeVar('D',bound=BaseDocument)

ClientMode  = Literal['async','sync']

class MongoClientStore:

    def __init__(self,):
        self.clients:dict[CredentialName,dict[ClientMode,Union[MongoClient,AsyncIOMotorClient]]] = {}
    
    def get_client(self,name:CredentialName,mode:ClientMode='async'):
        if name not in self.clients:
            raise MongoClientDataDoesNotExistError(name)
        
        if mode not in self.clients[name]:
            raise MongoClientModeDoesNotExistError(name,mode)
        
        return self.clients[name][mode]
    
    def add_client(self,name:CredentialName,uri:str,mode:ClientMode|None  = None):
        try:
            self.get_client(name,mode)
            raise MongoClientAlreadyExistError(name,mode)
        except :
            ...
        
        self.clients[name] = {}
        if mode == None or mode == 'sync':
            self.clients[name]['sync'] = MongoClient(uri)
        elif mode == None or mode == 'async':
            self.clients[name]['async'] = AsyncIOMotorClient(uri)
        else:
            ...
    
    def get_database(self,name:CredentialName,mode:ClientMode='async',database=MongooseDBConstant.DATABASE_NAME):
        return self.get_client(name,mode)[database]
    
    def get_collection(self,name:CredentialName,collection:str,mode:ClientMode='async',database=MongooseDBConstant.DATABASE_NAME):
        return self.get_database(name,mode,database)[collection]
    
    def iterator(self,mode:ClientMode|None = None):
        for n,m in self.clients.items():
            for t,client in m.items():
                if mode==None or t ==mode:
                    yield n,client

    def clear(self):
        self.clients.clear()


@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)])     
class MongooseService(TempCredentialsDatabaseService):

    def __init__(
        self,
        configService: ConfigService,
        fileService: FileService,
        vaultService: VaultService,
    ):
        super().__init__(configService, fileService,vaultService,VaultTTLSyncConstant.MONGODB_AUTH_TTL)

        self.client_store = MongoClientStore()
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
    
    def sync_find(self,collection:str,model:Type[D],filter={},projection:dict={},return_model=False,as_subset_model=False,filter_out=False)->list[D | dict]:
        
        filter['_class_id'] = {"$regex": f"{model.__name__}$" }

        if collection not in self.mongoConstant.available_collection:
            raise MongoCollectionDoesNotExists(collection,model.__class__.__name__)

        segment = self.get_credentials_name(model)

        mongo_collection = self.client_store.get_collection(segment,collection,'sync')
        docs = mongo_collection.find(filter,projection).to_list()

        if issubclass(model,BaseDocument) and return_model and as_subset_model:
            model = subset_model(model,model.__name__,optional=False,__cache__=True) 
        
        if not return_model:
            return docs
        
        if not filter_out:
            return  [model.model_construct(**doc) for doc in docs]

        _docs = []
        for doc in docs:
            try:
                m = model(**doc)
                _docs.append(m)
            except:
                ...
        
        return _docs
                
    ##################################################
    # Document integrity
    ##################################################

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
    
    async def condition_satisfaction(self,document:BaseDocument | dict):
        
        if not document._condition:
            return

        for mc in document._condition:
            
            if isinstance(document,BaseDocument):
                profile_dump = document.model_dump(mode='json')    
            else:
                profile_dump = document

            if not validate_filter(mc,profile_dump):
                continue

            count = await self.count(document.__class__,mc['filter'])
            if mc['method'] != 'simple-number-validation':
                raise DocumentConditionWrongMethodError

            if simple_number_validation(count,mc['rule']):
                raise DocumentAddConditionError(message =mc.get('message',None), detail=mc.get('detail',None))
            
            if not mc.get('force',False):
                return

            for k,v in mc['filter'].items():
                if not isinstance(v,(str,int,float,bool,list,dict)):
                    continue

                if isinstance(document,BaseDocument):
                    print(k,v)
                    setattr(document,k,v)
                else:
                    profile_dump[k] = v
                   
    ##################################################
    # Service lifecycle
    ##################################################

    def build(self, build_state=DEFAULT_BUILD_STATE):
        try:
            self.db_connection()
            for n,client in self.client_store.iterator('sync'):
                client.admin.command("ping")

            if build_state == DEFAULT_BUILD_STATE:
                super().build(build_state)
                
        except ConnectionFailure as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB connection error: {e}")

        except ConfigurationError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB configuration error: {e}")

        except ServerSelectionTimeoutError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"MongoDB server selection timeout: {e}")
        
        except PyMongoError as e:
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f'MongoDB error: {e._message}')

        except Exception as e:
            print(e)
            if build_state == DEFAULT_BUILD_STATE:
                raise BuildFailureError(f"Unexpected error: {e}")

    def db_connection(self):
        # fetch fresh creds from Vault
        self.client_store.clear()
        self.add_credentials(VaultConstant.MONGO_ROLE,'default')
        self.add_credentials(VaultConstant.MONGO_ROLE,AGENTIC_CREDS)

        self.client_store.add_client('default',self.mongo_uri())
        self.client_store.add_client(AGENTIC_CREDS,self.mongo_uri(AGENTIC_CREDS))

    async def _creds_rotator(self):
        self.close_connection()
        self.db_connection()
        await self.init_connection()
    
    def revoke_lease(self):
        super().revoke_lease()
        super().revoke_lease(AGENTIC_CREDS)

    def close_connection(self):
        try:
            for n,c in self.client_store.iterator():
                c.close()
        except Exception as e:
            ...

    async def init_connection(self,):
        agentic_doc = [doc for doc in self._documents if doc in AgenticConstant.AGENTIC_COLLECTIONS ]
        default_doc = [doc for doc in self._documents if doc not in AgenticConstant.AGENTIC_COLLECTIONS ]
        
        default_db = self.client_store.get_database('default')
        agentic_db = self.client_store.get_database(AGENTIC_CREDS)

        await init_beanie(database=agentic_db,document_models=agentic_doc,)
        await init_beanie(database=default_db,document_models=default_doc,)

    def register_document(self,*documents):
        temp = set()
        temp.update(self._documents)
        temp.update(list(documents))
        self._documents = list(temp)

    @asynccontextmanager
    async def transaction(self,name:CredentialName='default', retries=1,timeout=5,wait=1,lock:ServiceLockType='none'):
        lock = lock or 'none'
        async with self.lock(lock):
            client = self.client_store.get_client(name)
            async with await client.start_session() as session:
                for attempt in range(retries):
                    try:
                        async with session.start_transaction() as tr:
                            yield session,tr
                        break
                    except (ConnectionFailure, OperationFailure):
                        if attempt == retries - 1:
                            raise
                        else:
                            if wait:
                                await asyncio.sleep(wait)

    ##################################################
    # Connection string
    ##################################################
    def mongo_uri(self,name:CredentialName='default'):
        replica = self.configService.getenv('MONGO_REPLICA_NAME','notifyr-0')
        return f"mongodb://{self.db_user(name)}:{self.db_password(name)}@{self.configService.MONGO_HOST}:27017/{MongooseDBConstant.DATABASE_NAME}?replicaSet={replica}"
    
    def get_credentials_name(self,model:Type[D]|D)->CredentialName:
        return 'default' if model._collection not in AgenticConstant.AGENTIC_COLLECTIONS else AGENTIC_CREDS

    ##################################################
    # Healthcheck
    ##################################################
    
    def destroy(self, destroy_state = ...):
        self.close_connection()
    