import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import List, Literal, Type, TypeVar, Union
from pymongo.errors import ConnectionFailure,ConfigurationError, PyMongoError, ServerSelectionTimeoutError
from pymongo import MongoClient
from app.classes.mongo import BaseDocument, MongoCondition, simple_number_validation, validate_filter
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service, ServiceLockType
from app.errors.service_error import BuildFailureError
from app.errors.db_error import *
from beanie import Document, PydanticObjectId, init_beanie
from app.services.config_service import ConfigService
from app.services.database.base_db_service import CredentialConfig, CredentialName, ExportRoleFunc, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.timer_service import TimerService
from app.services.vault_service import VaultService
from app.utils.constant import HostConstant, MongooseDBConstant, SetupRootConstant, VaultConstant, VaultTTLSyncConstant
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, OperationFailure

from app.utils.globals import APP_MODE, ApplicationMode
from app.utils.helper import subset_model
from app.utils.toolbox import RunInThreadPool

AGENTIC_CREDS='agentic'
JOBS_CREDS='jobs'
CREDIT_CREDS='credit'

CREDENTIALS_SET:set[CredentialName] = {'default',AGENTIC_CREDS,JOBS_CREDS,CREDIT_CREDS} 

D = TypeVar('D',bound=BaseDocument)

ClientMode  = Literal['async','sync']

DB_MAP:dict[CredentialName,str]= {
    'default':MongooseDBConstant.DEFAULT_DATABASE_NAME,
    AGENTIC_CREDS:MongooseDBConstant.AGENTIC_DATABASE_NAME,
    JOBS_CREDS:MongooseDBConstant.JOB_DATABASE_NAME,
    CREDIT_CREDS:MongooseDBConstant.CREDIT_DATABASE_NAME
}

MONGO_CRED_NAME_TO_ROLE_MAP:dict[CredentialName,tuple[str,str]] = {
    'default': ('app', None),
    AGENTIC_CREDS: ('agentic', None),
    JOBS_CREDS: ('app','jobs'),
    CREDIT_CREDS: ('app','credit') # NOTE: Subject to change
}

export = ExportRoleFunc(MONGO_CRED_NAME_TO_ROLE_MAP)

class MongoClientStore:

    def __init__(self):
        self.clients:dict[CredentialName,dict[ClientMode,Union[MongoClient,AsyncIOMotorClient]]] = {}
    
    def get_client(self,name:CredentialName,mode:ClientMode='async'):
        if name not in self.clients:
            raise MongoClientNameDoesNotExistError(name)
        
        if mode not in self.clients[name]:
            raise MongoClientModeDoesNotExistError(name,mode)
        
        return self.clients[name][mode]
    
    def add_client(self,name:CredentialName,uri:str,mode:ClientMode|None = None):
        try:
            self.get_client(name,mode)
            raise MongoClientAlreadyExistError(name,mode)
        except :
            ...

        self.clients[name] = {}
        if mode == None or mode == 'sync':
            self.clients[name]['sync'] = MongoClient(uri)
        if mode == None or mode == 'async':
            self.clients[name]['async'] = AsyncIOMotorClient(uri)
    
    def get_database(self,name:CredentialName,mode:ClientMode='async'):
        database=DB_MAP[name]
        return self.get_client(name,mode)[database]
    
    def get_collection(self,name:CredentialName,collection:str,mode:ClientMode='async'):
        return self.get_database(name,mode)[collection]
    
    def iterator(self,mode:ClientMode|None = None):
        for n,m in self.clients.items():
            for t,client in m.items():
                if mode==None or t ==mode:
                    yield n,client
    
    def factory(self,uri:str,mode:ClientMode):
        match mode:
            case "sync":
                return MongoClient(uri)
            case 'async':
                return AsyncIOMotorClient(uri)
            case _:
                raise ValueError(f"Unsupported client mode: {mode}")
    
    def clear(self):
        self.clients.clear()


@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)])     
class MongooseService(TempCredentialsDatabaseService):

    def __init__(
        self,
        configService: ConfigService,
        fileService: FileService,
        vaultService: VaultService,
        timerService:TimerService
    ):
        super().__init__(configService, fileService,vaultService,timerService,'static',VaultTTLSyncConstant.MONGODB_AUTH_TTL)

        self.client_store = MongoClientStore()
        self._documents = []
        self.mongoConstant = MongooseDBConstant()
        self.MONGO_CRED_NAME_TO_HOST = {
            'default':HostConstant.MONGOOSE_HOST,
            AGENTIC_CREDS:HostConstant.MONGOOSE_HOST,
            JOBS_CREDS:self.configService.MONGO_HOST,
            CREDIT_CREDS:HostConstant.MONGOOSE_HOST,
            }

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

    async def delete(self, model: D,*args,**kwargs):
        return await model.delete(*args,**kwargs)

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
        if build_state == SetupRootConstant.ROOT_BUILD_STATE:
            return

        try:
            self.generate_credentials()
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
        self.client_store.add_client('default',self.compute_url(self.MONGO_CRED_NAME_TO_HOST['default'],DB_MAP['default'],authSource='admin'))
        self.client_store.add_client(JOBS_CREDS,self.compute_url(self.MONGO_CRED_NAME_TO_HOST[JOBS_CREDS],DB_MAP[JOBS_CREDS],name=JOBS_CREDS,authSource='notifyr'))
        self.client_store.add_client(AGENTIC_CREDS,self.compute_url(self.MONGO_CRED_NAME_TO_HOST[AGENTIC_CREDS],DB_MAP[AGENTIC_CREDS],AGENTIC_CREDS,authSource='admin'))

    def generate_credentials(self):
        self.add_credentials(VaultConstant.MONGO_ROLE,'default',**export('default'))
        self.add_credentials(VaultConstant.MONGO_ROLE,JOBS_CREDS,**export(JOBS_CREDS))
        self.add_credentials(VaultConstant.MONGO_ROLE,AGENTIC_CREDS,**export(AGENTIC_CREDS))

    async def _creds_rotator(self):
        self.close_connection()
        await RunInThreadPool(self.generate_credentials)()
        self.db_connection()
        await self.init_connection()
    
    def revoke_lease(self,name:CredentialName=None):
        if name == None or name == 'default':
            super().revoke_lease()
        if name == None or name == AGENTIC_CREDS:
            super().revoke_lease(AGENTIC_CREDS)
        if name == None or name == JOBS_CREDS:
            super().revoke_lease(JOBS_CREDS)

    def close_connection(self):
        try:
            for n,c in self.client_store.iterator():
                c.close()
        except Exception as e:
            ...

    async def init_connection(self,):
        agentic_doc = [doc for doc in self._documents if doc in MongooseDBConstant.AGENTIC_COLLECTIONS ]
        default_doc = [doc for doc in self._documents if doc not in MongooseDBConstant.DEFAULT_COLLECTIONS ]
        
        default_db = self.client_store.get_database('default')
        agentic_db = self.client_store.get_database(AGENTIC_CREDS)
    
        await init_beanie(database=agentic_db,document_models=agentic_doc,)
        await init_beanie(database=default_db,document_models=default_doc,)

        if self.configService.JOBSTORE_DB == 'mongodb':
            tasks_doc = [doc for doc in self._documents if doc not in MongooseDBConstant.JOB_COLLECTIONS ]
            tasks_db = self.client_store.get_database(JOBS_CREDS)
            await init_beanie(database=tasks_db,document_models=tasks_doc)

    def register_document(self,*documents):
        temp = set()
        temp.update(self._documents)
        temp.update(list(documents))
        self._documents = list(temp)

    ##################################################
    # Connectivity
    ##################################################

    @contextmanager
    def mongo_dynamic_synccontext(self,name:CredentialName,transaction=False):
        config:CredentialConfig = self.configuration(name)
        creds = self.vaultService.database_engine.generate_credentials(VaultConstant.MONGO_ROLE,config['prefix'],config['suffix'],mode='dynamic')
        uri = self.compute_url(config['host'],config['database'],username=creds['data']['username'],password=creds['data']['password'])
        client:MongoClient = self.client_store.factory(uri,mode='sync')
        yield client
        client.close()
        self.vaultService.revoke_lease(creds['lease_id'])

    @asynccontextmanager
    async def mongo_dynamic_asynccontext(self,name:CredentialName):
        config:CredentialConfig = self.configuration(name)
        creds = self.vaultService.database_engine.generate_credentials(VaultConstant.MONGO_ROLE,config['prefix'],config['suffix'],mode='dynamic')
        uri = self.compute_url(config['host'],config['database'],username=creds['data']['username'],password=creds['data']['password'])
        client:AsyncIOMotorClient = self.client_store.factory(uri,mode='async')
        yield client
        await client.close()
        self.vaultService.revoke_lease(creds['lease_id'])

    @asynccontextmanager
    async def transaction(self,name:CredentialName='default', retries=1,timeout=5,wait=1,lock:ServiceLockType='none',conn=None):
        if name not in CREDENTIALS_SET:
            raise VaultCredentialNameDoesNotExistError(name)

        lock = lock or 'none'
        async with self.lock(lock):
            if not conn:
                client = self.client_store.get_client(name)
            else:
                client = conn
            async with await client.start_session() as session:
                for attempt in range(retries):
                    try:
                        async with session.start_transaction() as tr:
                            yield session,tr
                        break
                    except (ConnectionFailure, OperationFailure) as e:
                        if attempt == retries - 1:
                            raise MongoTransactionFailureError(name,attempt,...,e)
                        else:
                            if wait:
                                await asyncio.sleep(wait)
                

    ##################################################
    # Connection string
    ##################################################

    def compute_url(self,host:str,database=MongooseDBConstant.JOB_DATABASE_NAME,name:CredentialName='default',authSource=None,username:str=None,password:str=None):
        replica = self.configService.getenv('MONGO_REPLICA_NAME','notifyr-0')
        authSource = f'authSource={authSource}&' if authSource else ''
        return f"mongodb://{username or self.db_user(name)}:{password or self.db_password(name)}@{host}:27017/{database}?{authSource}replicaSet={replica}"
    
    def get_credentials_name(self,model:Type[D]|D)->CredentialName:

        if model._collection in MongooseDBConstant.DEFAULT_COLLECTIONS:
            return 'default'

        if model._collection in MongooseDBConstant.AGENTIC_COLLECTIONS:
            return AGENTIC_CREDS

        if model._collection in MongooseDBConstant.JOB_COLLECTIONS:
            return JOBS_CREDS

        raise MongoCollectionDoesNotExists(model._collection)

    def configuration(self,name:CredentialName)->CredentialConfig:
        if name not in CREDENTIALS_SET:
            raise VaultCredentialNameDoesNotExistError(name)
        host = self.MONGO_CRED_NAME_TO_HOST.get(name,HostConstant.MONGOOSE_HOST)
        database = DB_MAP.get(name,MongooseDBConstant.DEFAULT_DATABASE_NAME)
        prefix,suffix = MONGO_CRED_NAME_TO_ROLE_MAP.get(name,(None,None))
        return {
            'host':host,
            'database':database,
            'prefix':prefix,
            'suffix':suffix,
        }

    ##################################################
    # Healthcheck
    ##################################################
    
    def destroy(self, destroy_state = ...):
        self.close_connection()
    