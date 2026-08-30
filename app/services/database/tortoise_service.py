import psycopg2
from tortoise import Tortoise
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import CredentialName, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import HostConstant, PostgresConstant, VaultConstant, VaultTTLSyncConstant
from app.utils.toolbox import RunInThreadPool

CLIENT_CREDS='client'

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
        self.add_credentials(VaultConstant.POSTGRES_ROLE,CLIENT_CREDS,suffix='client')

    def compute_url(self,host:str,port:int=5432,creds:CredentialName='default',database=PostgresConstant.DEFAULT_DATABASE_NAME):
        return f'postgres://{self.db_user(creds)}:{self.db_password(creds)}@{host}:{port}/{database}'

    def build_configuration(self):
        return {
            "connections": {
                "default": self.compute_url(self.configService.POSTGRES_HOST),
                CLIENT_CREDS: self.compute_url(
                    HostConstant.POSTGRES_HOST,
                    creds=CLIENT_CREDS,
                    database=PostgresConstant.CLIENT_DATABASE_NAME,
                ),
            },
            "apps": {
                "default": {
                    "models": [
                        "app.models.orm.contacts_model",
                        "app.models.email_model",
                        "app.models.orm.link_model",
                        "app.models.orm.twilio_model",
                    ],
                    "default_connection": "default",
                },
                CLIENT_CREDS: {
                    "models": ["app.models.security_model"],
                    "default_connection": CLIENT_CREDS,
                },
            },
        }

    def init_sync_connection(self):
        self.sync_conn = psycopg2.connect(
                            dbname=PostgresConstant.CLIENT_DATABASE_NAME,
                            user=self.db_user(CLIENT_CREDS),
                            password=self.db_password(CLIENT_CREDS),
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

    async def _creds_rotator(self):
        await self.close_connections()
        await RunInThreadPool(self.generate_credentials)()
        await self.init_connection(False)
        await RunInThreadPool(self.init_sync_connection)()

