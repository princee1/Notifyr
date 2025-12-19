from app.definition._service import LinkDep, Service
from app.errors.service_error import BuildFailureError, BuildWarningError
from app.services.config_service import ConfigService
from app.services.database.base_db_service import TempCredentialsDatabaseService
from app.services.file.file_service import FileService
from app.services.secret_service import HCVaultService
from app.utils.constant import RabbitMQConstant


@Service(links=[LinkDep(HCVaultService,to_build=True,to_destroy=True)]) 
class RabbitMQService(TempCredentialsDatabaseService):
    
    def __init__(self, configService:ConfigService, fileService:FileService, vaultService:HCVaultService):
        super().__init__(configService, fileService, vaultService, 60*60*24*29)
    
    def verify_dependency(self):
        if self.configService.CELERY_BROKER == 'redis':
            raise BuildWarningError
    
    def build(self, build_state = ...):
        import pika
        self.creds=self.vaultService.rabbitmq_engine.generate_credentials()
        credentials = pika.PlainCredentials(username=self.db_user,password=self.db_password)

        params = pika.ConnectionParameters(
            host=self.configService.RABBITMQ_HOST,
            port=5672,
            virtual_host=RabbitMQConstant.CELERY_VIRTUAL_HOST,
            credentials=credentials,
            connection_attempts=1,      # don’t retry
            socket_timeout=5,           # 5 second timeout
            blocked_connection_timeout=5,
        )

        try:
            connection = pika.BlockingConnection(params)
            connection.close()
            super().build()

        except Exception as e:
            print(e)
            print(e.__class__)
            print(e.args)
            self.configService.CELERY_BROKER = 'redis'
            raise BuildFailureError
    