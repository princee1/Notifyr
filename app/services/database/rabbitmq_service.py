from app.definition._service import DEFAULT_BUILD_STATE, LinkDep, Service
from app.errors.service_error import BuildFailureError, BuildWarningError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import BrokerService, TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.vault_service import VaultService
from app.utils.constant import RabbitMQConstant
from app.utils.toolbox import RunInThreadPool


@Service(links=[LinkDep(VaultService,to_build=True,to_destroy=True)]) 
class RabbitMQService(TempCredentialsDatabaseService,BrokerService):
    
    def __init__(self, configService:ConfigService, fileService:FileService, vaultService:VaultService):
        super().__init__(configService, fileService, vaultService,60*60*24*29)
    
    def verify_dependency(self):
        if self.configService.CELERY_BROKER_PROVIDER == 'redis':
            raise BuildWarningError("Redis is set as the broker; skipping RabbitMQ setup.")
    
    def generate_credentials(self):
        if 'default' in self.creds:
            self.revoke_lease()
        self.creds['default']=self.vaultService.rabbitmq_engine.generate_credentials()

    def build(self, build_state = ...):
        self.generate_credentials()
        import pika
        credentials = pika.PlainCredentials(username=self.db_user(),password=self.db_password())

        params = pika.ConnectionParameters(
            host=self.configService.RABBITMQ_HOST,
            port=5672,
            virtual_host=RabbitMQConstant.NOTIFYR_VIRTUAL_HOST,
            credentials=credentials,
            connection_attempts=1,      # don’t retry
            socket_timeout=5,           # 5 second timeout
            blocked_connection_timeout=5,
        )

        try:
            connection = pika.BlockingConnection(params)
            connection.close()
            
            if build_state == DEFAULT_BUILD_STATE:
                super().build(build_state)

        except Exception as e:
            self.configService.CELERY_BROKER_PROVIDER = 'redis'
            raise BuildFailureError("Failed to connect to RabbitMQ with generated credentials. Ensure RabbitMQ is running and accessible.") from e

    def compute_url(self):
        return f"amqp://{self.db_user()}:{self.db_password()}@{self.configService.RABBITMQ_HOST}:5672/{RabbitMQConstant.NOTIFYR_VIRTUAL_HOST}"
        
    def compute_broker_url(self):
        if self.configService.CELERY_BROKER_PROVIDER == 'redis':
            return None
        return self.compute_url()

    async def _creds_rotator(self):
        await RunInThreadPool(self.generate_credentials)()
