import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Callable, Literal, Type, TypeVar
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from tortoise import BaseDBAsyncClient, Tortoise,connections
from tortoise.connection import get_connection
from tortoise.context import TortoiseContext
from tortoise.models import Model
from app.classes.vault_engine import CredentialsMode
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service, ServiceLockType
from app.errors.db_error import TortoiseContextAlreadyExistError, TortoiseContextDoesNotExistError, TortoiseContextNotSetupError, TortoiseTransactionFailureError, VaultCredentialNameDoesNotExistError
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import CredentialConfig, CredentialName, ExportRoleFunc, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.timer_service import TimerService
from app.services.vault_service import VaultService
from app.utils.constant import HostConstant, PostgresConstant, SetupRootConstant, VaultConstant, VaultTTLSyncConstant
from app.utils.toolbox import RunInThreadPool
from tortoise.backends.base.client import TransactionContext
from tortoise.exceptions import OperationalError,ConfigurationError,IntegrityError


SECURITY_CREDS='security'
CREDENTIALS_SET:set[CredentialName] = {'default',SECURITY_CREDS}

NOTIFYR_MODELS = [
                    "app.models.orm.contacts_model",
                    "app.models.orm.email_model",
                    "app.models.orm.link_model",
                    "app.models.orm.twilio_model",
                ]

SECURITY_MODELS = ['app.models.orm.security_model']
APP_TO_MODEL_MAP = {
    PostgresConstant.NOTIFYR_APP:NOTIFYR_MODELS,
    PostgresConstant.SECURITY_APP:SECURITY_MODELS
}
R = TypeVar('R',bound=Model)

DB_MAP: dict[CredentialName,str] = {
    'default':PostgresConstant.NOTIFYR_APP,
    SECURITY_CREDS:PostgresConstant.SECURITY_APP
}

PG_CRED_NAME_TO_ROLE_MAP: dict[CredentialName,tuple[str,str]] = {
    'default':('app',None),
    'security':('app','security')
}

pg_role_export = ExportRoleFunc(PG_CRED_NAME_TO_ROLE_MAP)

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

    def __init__(self, configService: ConfigService,vaultService:VaultService,fileService:FileService,timerService:TimerService):
        super().__init__(configService,fileService,vaultService,timerService,'static',VaultTTLSyncConstant.POSTGRES_AUTH_TTL)
        self.contextStore = TortoiseContextStore()
        self.PG_CRED_NAME_TO_HOST = {
            'default':self.configService.POSTGRES_HOST,
            SECURITY_CREDS:HostConstant.POSTGRES_HOST
        }

    def build(self,build_state=DEFAULT_BUILD_STATE):
        if build_state == SetupRootConstant.ROOT_BUILD_STATE:
            return

        try:
            self.generate_credentials()
            for name in CREDENTIALS_SET:
                with self.pg_dynamic_synccontext(name,mode='static') as conn:
                    ...

            if build_state == DEFAULT_BUILD_STATE:
                super().build(build_state)
        except Exception as e:
            raise BuildFailureError(f"Error during Tortoise ORM connection: {e}")

    def generate_credentials(self):
        self.add_credentials(VaultConstant.POSTGRES_ROLE,'default',**pg_role_export('default'))
        self.add_credentials(VaultConstant.POSTGRES_ROLE,SECURITY_CREDS,**pg_role_export(SECURITY_CREDS))

    def compute_url(self,host:str,port:int=5432,creds:CredentialName='default',database=PostgresConstant.DEFAULT_DATABASE_NAME,username:str=None,password:str=None):
        return f'postgres://{username or self.db_user(creds)}:{password or self.db_password(creds)}@{host}:{port}/{database}'

    def fetch(self,model:Type[R],projection:list[str]=None,mode:Literal['json','orm']='json',listing:Literal['list','generator','dict']='generator',key=None):
        proj = projection or []
        if mode=='orm' and projection:
            raise ValueError('Cannot build an ORM from a partial json mapping')

        if listing =='dict' and not key:
            raise ValueError('Key should be specified if the listing is a dict')
            
        columns = list(set(proj))
        if columns:
            columns = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
        else:
            columns = sql.SQL("*")
        
        query = sql.SQL("""SELECT {columns} FROM {schema}.{table}""").format(columns=columns,
                schema=sql.Identifier(model.Meta.schema),
                table=sql.Identifier(model.Meta.table),)
        objs = []

        segment = self.get_credentials_name(model)

        with self.pg_dynamic_synccontext(segment) as cur:
            cur.execute(query)
            response = {} if listing == 'dict' else []
            objs = cur.fetchall()

        for obj in objs:
            k = None if key == None else obj[key]
            obj=dict(obj)
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
        self.contextStore.clear()

    @contextmanager
    def sync_context(self,conn,transaction=False):
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur

    @contextmanager
    def pg_dynamic_synccontext(self,name:CredentialName,transaction:bool=False,mode:CredentialsMode='dynamic'):
        config:CredentialConfig = self.configuration(name)
        if mode == 'dynamic':
            creds = self.vaultService.database_engine.generate_credentials(VaultConstant.POSTGRES_ROLE,config['prefix'],config['suffix'],'dynamic')
        else:
            creds = self.get_credentials(name)
        url = self.compute_url(config['host'],database=config['database'],username=creds['data']['username'],password=creds['data']['password'])
        conn = psycopg2.connect(url)
        with self.sync_context(conn, transaction=transaction) as cur:
            yield cur
        conn.close()
        if mode == 'dynamic':
            self.vaultService.revoke_lease(creds['lease_id'])

    @asynccontextmanager
    async def pg_dynamic_asynccontext(self,name:CredentialName,transaction:bool=False,mode:CredentialsMode='dynamic'):
        config:CredentialConfig = self.configuration(name)
        if mode == 'dynamic':
            creds = self.vaultService.database_engine.generate_credentials(VaultConstant.POSTGRES_ROLE,config['prefix'],config['suffix'],'dynamic')
        else:
            creds = self.get_credentials(name)
        url = self.compute_url(config['host'],database=config['database'],username=creds['data']['username'],password=creds['data']['password'])
        app = DB_MAP[name]
        models = APP_TO_MODEL_MAP[app]
        async with TortoiseContext() as ctx:
            config = {'connections':{'default':url},'apps':{app:{'models':models,'default_connection':'default'}}}
            await ctx.init(config=config)
            if transaction:
                yield ctx.connections.get('default')
            else:
                yield ctx
        if mode == 'dynamic':
            self.vaultService.revoke_lease(creds['lease_id'])

    def get_credentials_name(self,model:Type[R])->CredentialName:
        if model.Meta.app == PostgresConstant.NOTIFYR_APP:
            return 'default'
        if model.Meta.app == PostgresConstant.SECURITY_APP:
            return SECURITY_CREDS

    def configuration(self, name:CredentialName)->CredentialConfig:
        if name not in CREDENTIALS_SET:
            raise VaultCredentialNameDoesNotExistError(name)
        host = self.PG_CRED_NAME_TO_HOST.get(name,HostConstant.POSTGRES_HOST)
        database = DB_MAP.get(name,PostgresConstant.DEFAULT_DATABASE_NAME)
        prefix,suffix = PG_CRED_NAME_TO_ROLE_MAP.get(name,(None,None))
        return CredentialConfig(host=host, database=database, prefix=prefix, suffix=suffix)

    async def _creds_rotator(self):
        await self.close_connections()
        await RunInThreadPool(self.generate_credentials)()
        await self.init_connection(False)
    
    @asynccontextmanager
    async def transaction(self,name:CredentialName='default',retries=1,timeout=5,wait=1,silent=False,lock:ServiceLockType='none',conn:None|BaseDBAsyncClient=None):
        if conn is None:
            if name not in CREDENTIALS_SET:
                raise VaultCredentialNameDoesNotExistError(name)
            connection = 'notifyr' if name == 'default' else 'security'
        
        async with self.lock(lock):
            for attempts in range(retries):
                if conn is None:
                    conn = get_connection(connection)
                async with (conn._in_transaction()) as ctx:
                    try:
                        yield ctx
                        break
                    except (OperationalError,IntegrityError) as e:
                        if attempts == retries:
                            if silent:
                                return
                            raise TortoiseTransactionFailureError(name,retries,error=e)
                        if wait:
                            asyncio.sleep(wait)
                        continue
            
    @asynccontextmanager
    async def connection(self,credentials:CredentialName='default',lock:ServiceLockType='none'):
        async with self.lock(lock):
            conn = self.contextStore.get_connection(credentials) 
            yield conn

    