import psycopg2
from tortoise import Tortoise
from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import CredentialName, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import PostgresConstant, VaultConstant, VaultTTLSyncConstant
from app.utils.toolbox import RunInThreadPool


@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)])
class TortoiseConnectionService(TempCredentialsDatabaseService):

    def __init__(self, configService: ConfigService,vaultService:VaultService,fileService:FileService):
        super().__init__(configService,fileService,vaultService,VaultTTLSyncConstant.POSTGRES_AUTH_TTL)

    def build(self,build_state=-1):
        try:
            self.generate_credentials()
            conn = psycopg2.connect(
                dbname=PostgresConstant.DEFAULT_DATABASE_NAME,
                user=self.db_user(),
                password=self.db_password(),
                host=self.configService.POSTGRES_HOST,
                port=5432
            )
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
        self.add_credentials(VaultConstant.POSTGRES_ROLE,...)

    def compute_url(self,host:str,port:int=5432,creds:CredentialName='default',database=PostgresConstant.DEFAULT_DATABASE_NAME):
        return f'postgres://{self.db_user(creds)}:{self.db_password(creds)}@{host}:{port}/{database}'

    @property
    def postgres_uri(self):
        return self.compute_url(self.configService.POSTGRES_HOST)
        
    async def init_connection(self,close=False):
        if close:
            await self.close_connections()
        await Tortoise.init(
            db_url=self.postgres_uri,
            modules={"models": ["app.models.orm.contacts_model","app.models.security_model","app.models.email_model","app.models.orm.link_model","app.models.orm.twilio_model"]},
        )

    async def close_connections(self):
        await Tortoise.close_connections()    

    async def _creds_rotator(self):
        await self.close_connections()
        await RunInThreadPool(self.generate_credentials)()
        await self.init_connection(False)

