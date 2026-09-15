import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Literal, Type, TypeVar
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from tortoise import Tortoise,connections
from tortoise.connection import get_connection
from tortoise.context import TortoiseContext
from tortoise.models import Model
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service, ServiceLockType
from app.errors.db_error import TortoiseContextAlreadyExistError, TortoiseContextDoesNotExistError, TortoiseContextNotSetupError, TortoiseTransactionFailureError, VaultCredentialNameDoesNotExistError
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import CredentialName, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import HostConstant, PostgresConstant, VaultConstant, VaultTTLSyncConstant
from app.utils.toolbox import RunInThreadPool
from tortoise.transactions import in_transaction
from tortoise.exceptions import OperationalError,ConfigurationError,IntegrityError
from pydantic import BaseModel


SECURITY_CREDS='security'

CREDENTIALS_SET:set[CredentialName] = {'default',SECURITY_CREDS}

NOTIFYR_MODELS = [
                    "app.models.orm.contacts_model",
                    "app.models.orm.email_model",
                    "app.models.orm.link_model",
                    "app.models.orm.twilio_model",
                ]

SECURITY_MODELS = ['app.models.orm.security_model']
R = TypeVar('R',bound=Model)


class TortoiseContextStore:
    
    def __init__(self):
        self.store:dict[CredentialName,TortoiseContext] = {}

    async def add_client(self,credential:CredentialName,context:TortoiseContext):
        if credential in self.store:
            raise TortoiseContextAlreadyExistError(credential)

        self.store[credential] = context

        print(self.store[credential].apps.apps)
        print(self.store[credential].connections._get_storage())
        #await self.get_connection('default').create_connection(True)

    
    def clear(self):
        self.store.clear()

    def get_context(self,credential:CredentialName):
        if credential not in self.store:
            raise TortoiseContextDoesNotExistError(credential)

        return self.store[credential]

    def get_connection(self,credential:CredentialName):
        if credential not in self.store:
            raise TortoiseContextDoesNotExistError(credential)

        return self.store[credential].connections.get('default')

    def iter(self):
        for _,context in self.store.items():
            yield context

@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)])
class TortoiseConnectionService(TempCredentialsDatabaseService):

    def __init__(self, configService: ConfigService,vaultService:VaultService,fileService:FileService):
        super().__init__(configService,fileService,vaultService,VaultTTLSyncConstant.POSTGRES_AUTH_TTL)
        self.contextStore = TortoiseContextStore()

    def build(self,build_state=-1):
        try:
            self.generate_credentials()
            self.init_sync_connection()
            conn = psycopg2.connect(
                dbname=PostgresConstant.DEFAULT_DATABASE_NAME,
                user=self.db_user(),
                password=self.db_password(),
                host=self.configService.POSTGRES_HOST,
                port=5432)
            if build_state == DEFAULT_BUILD_STATE:
                super().build(build_state)
        except Exception as e:
            raise BuildFailureError(f"Error during Tortoise ORM connection: {e}")
        finally:
            try:
                if conn:
                    conn.close()
            except:
                ...

    def generate_credentials(self):
        self.add_credentials(VaultConstant.POSTGRES_ROLE)
        self.add_credentials(VaultConstant.POSTGRES_ROLE,SECURITY_CREDS,suffix='security')

    def compute_url(self,host:str,port:int=5432,creds:CredentialName='default',database=PostgresConstant.DEFAULT_DATABASE_NAME):
        return f'postgres://{self.db_user(creds)}:{self.db_password(creds)}@{host}:{port}/{database}'

    def sync_find(self,model:Type[R],projection:list[str]=None,mode:Literal['json','orm']='json',listing:Literal['list','generator','dict']='generator',key=None):
        proj = projection or []
        if mode=='orm' and projection:
            raise ValueError('Cannot build an ORM from a partial json mapping')

        if listing =='dict' and not key:
            raise ValueError('Key should be specified if the listing is a dict')
            
        columns = list(set(proj))
        query = sql.SQL("""SELECT {columns} FROM {schema}.{table}""").format(columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                schema=sql.Identifier(model.Meta.schema),
                table=sql.Identifier(model.Meta.table),)
        with self.sync_context() as cur:
            cur.execute(query)
            response = {} if listing == 'dict' else []
            for obj in cur.fetchall():
                k = None if key == None else obj[key]
                if mode=='orm':
                    obj = model(**obj)
                match listing:
                    case 'generator':
                        yield obj
                    case 'list':
                        response.append(obj)
                    case 'dict':
                        response[k] = obj
            
            if listing != 'generator':
                return response

    def init_sync_connection(self):
        self.sync_conn = psycopg2.connect(
                            dbname=PostgresConstant.SECURITY_DATABASE_NAME,
                            user=self.db_user(SECURITY_CREDS),
                            password=self.db_password(SECURITY_CREDS),
                            host=HostConstant.POSTGRES_HOST,
                            port=5432
                        )

    def close_sync_connection(self):
        self.sync_conn.close()

    def build_configuration(self):
        security_url = self.compute_url(HostConstant.POSTGRES_HOST,creds=SECURITY_CREDS,database=PostgresConstant.SECURITY_DATABASE_NAME)
        notifyr_url = self.compute_url(self.configService.POSTGRES_HOST)

        config = {
            'connections': {'notifyr':notifyr_url,'security':security_url},
            'apps':{PostgresConstant.SECURITY_APP:{'models':SECURITY_MODELS,'default_connection':'security'},
                    PostgresConstant.NOTIFYR_APP:{'models':NOTIFYR_MODELS,'default_connection':'notifyr'}}
        }
        return config
    
    async def init_connection(self, close=False):

        if close:
            await self.close_connections()
        config = self.build_configuration()
        await Tortoise.init(config=config,_enable_global_fallback=True)
        # notifyrClient = connections.get('notifyr')
        # securityClient = connections.get('security')

        # securityContext = TortoiseContext()
        # securityContext.__enter__()
        # url = self.compute_url(HostConstant.POSTGRES_HOST,creds=SECURITY_CREDS,database=PostgresConstant.SECURITY_DATABASE_NAME)
        # config = {'connections':{'default':url},'apps':{PostgresConstant.SECURITY_APP:{'models':SECURITY_MODELS,'default_connection':'default'}}}
        # await securityContext.init(config = config)
        # await self.contextStore.add_client(SECURITY_CREDS,securityContext)

        # notifyrContext=TortoiseContext()
        # notifyrContext.__enter__()
        # url = self.compute_url(self.configService.POSTGRES_HOST)
        # config = {'connections':{'default':url},'apps':{PostgresConstant.NOTIFYR_APP:{'models':NOTIFYR_MODELS,'default_connection':'default'}}}
        # await notifyrContext.init(config=config)
        # await self.contextStore.add_client('default',notifyrContext)

    async def close_connections(self):
        for context in self.contextStore.iter():
            await context.close_connections()
        await Tortoise.close_connections()
        await RunInThreadPool(self.close_sync_connection)()  
        self.contextStore.clear()

    @contextmanager
    def sync_context(self):
        with self.sync_conn:
            with self.sync_conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur

    async def _creds_rotator(self):
        await self.close_connections()
        await RunInThreadPool(self.generate_credentials)()
        await self.init_connection(False)
        await RunInThreadPool(self.init_sync_connection)()
    
    @asynccontextmanager
    async def transaction(self,name:CredentialName='default',retries=1,timeout=5,wait=1,lock:ServiceLockType='none'):
        if name not in CREDENTIALS_SET:
            raise VaultCredentialNameDoesNotExistError(name)

        connection = 'notifyr' if name == 'default' else 'security'
        async with self.lock(lock):
            for attempts in range(retries):
                try:
                    async with get_connection(connection)._in_transaction() as ctx:
                        yield ctx
                    break
                except (OperationalError,IntegrityError) as e:
                    if attempts == retries:
                        raise TortoiseTransactionFailureError(name,retries,error=e)
                    if wait:
                        asyncio.sleep(wait)
                    continue
            
    @asynccontextmanager
    async def connection(self,credentials:CredentialName='default',lock:ServiceLockType='none'):
        async with self.lock(lock):
            conn = self.contextStore.get_connection(credentials) 
            yield conn
            