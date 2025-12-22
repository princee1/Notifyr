import psycopg2
from tortoise import Tortoise
from app.definition._service import LinkDep, Service
from app.errors.service_error import BuildFailureError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import TempCredentialsDatabaseService
from app.services.vault_service import VaultService
from app.utils.constant import VaultConstant, VaultTTLSyncConstant


@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)])
class TortoiseConnectionService(TempCredentialsDatabaseService):
    DATABASE_NAME = 'notifyr'

    def __init__(self, configService: ConfigService,vaultService:VaultService):
        super().__init__(configService, None,vaultService,VaultTTLSyncConstant.POSTGRES_AUTH_TTL)

    def build(self,build_state=-1):
        try:
            self.generate_creds()
            conn = psycopg2.connect(
                dbname=self.DATABASE_NAME,
                user=self.db_user,
                password=self.db_password,
                host=self.configService.POSTGRES_HOST,
                port=5432
            )
            super().build()
            self.generate_creds()
        except Exception as e:
            raise BuildFailureError(f"Error during Tortoise ORM connection: {e}")

        finally:
            try:
                if conn:
                    conn.close()
            except:
                ...

    def generate_creds(self):
        self.creds = self.vaultService.database_engine.generate_credentials(VaultConstant.POSTGRES_ROLE)
        
    @property
    def postgres_uri(self):
        return f"postgres://{self.db_user}:{self.db_password}@{self.configService.POSTGRES_HOST}:5432/{self.DATABASE_NAME}"
        
    async def init_connection(self,close=False):
        if close:
            await self.close_connections()
        await Tortoise.init(
            db_url=self.postgres_uri,
            modules={"models": ["app.models.contacts_model","app.models.security_model","app.models.email_model","app.models.link_model","app.models.twilio_model"]},
        )

    async def close_connections(self):
        await Tortoise.close_connections()    

    async def _creds_rotator(self):
        self.generate_creds()
        await self.init_connection(True)

