import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Literal
import psycopg2
from psycopg2 import sql
from tortoise import Tortoise
from tortoise.models import Model
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service, ServiceLockType
from app.errors.db_error import TortoiseTransactionFailureError, VaultCredentialNameDoesNotExistError
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

@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)])
class TortoiseConnectionService(TempCredentialsDatabaseService):

    def __init__(self, configService: ConfigService,vaultService:VaultService,fileService:FileService):
        super().__init__(configService,fileService,vaultService,VaultTTLSyncConstant.POSTGRES_AUTH_TTL)

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

    def build_configuration(self):
        return {
            "connections": {
                "default": self.compute_url(self.configService.POSTGRES_HOST),
                SECURITY_CREDS: self.compute_url(
                    HostConstant.POSTGRES_HOST,
                    creds=SECURITY_CREDS,
                    database=PostgresConstant.SECURITY_DATABASE_NAME,
                ),
            },
            "apps": {
                "default": {
                    "models": [
                        "app.models.orm.contacts_model",
                        "app.models.orm.email_model",
                        "app.models.orm.link_model",
                        "app.models.orm.twilio_model",
                    ],
                    "default_connection": "default",
                },
                SECURITY_CREDS: {
                    "models": ["app.models.orm.security_model"],
                    "default_connection": SECURITY_CREDS,
                },
            },
        }

    def sync_find(self,model:Model,projection:list[str]=None,mode:Literal['json','orm']='json',listing:Literal['list','generator']='generator'):
        proj = projection or []
        columns = list(set(proj))
        query = sql.SQL("""SELECT {columns}FROM {schema}.{table}""").format(columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                schema=sql.Identifier(model.Meta.schema),
                table=sql.Identifier(model.Meta.table),)
        with self.conn_ctx() as cur:
            cur.execute(query)
            response = []
            for obj in cur.fetchall():
                if listing == 'generator':
                    yield obj
                else:
                    response.append(obj)
            
            if listing == 'list':
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

    async def init_connection(self, close=False):
        if close:
            await self.close_connections()
        config = self.build_configuration()
        await Tortoise.init(config)

    async def close_connections(self):
        await Tortoise.close_connections()
        await RunInThreadPool(self.close_sync_connection)()  

    @contextmanager
    def conn_ctx(self):
        with self.sync_conn:
            with self.sync_conn.cursor() as cur:
                yield cur

    async def _creds_rotator(self):
        await self.close_connections()
        await RunInThreadPool(self.generate_credentials)()
        await self.init_connection(False)
        await RunInThreadPool(self.init_sync_connection)()
    
    @asynccontextmanager
    async def transaction(self,name:CredentialName,retries=1,timeout=5,wait=1,lock:ServiceLockType='none'):
        if name not in CREDENTIALS_SET:
            raise VaultCredentialNameDoesNotExistError(name)
        async with self.lock(lock):
            for attempts in range(retries):
                try:
                    async with in_transaction(connection_name=name) as ctx:
                        yield ctx
                    break
                except (OperationalError,IntegrityError) as e:
                    if attempts == retries:
                        raise TortoiseTransactionFailureError(name,retries,error=e)
                    if wait:
                        asyncio.sleep(wait)
                    continue
            

