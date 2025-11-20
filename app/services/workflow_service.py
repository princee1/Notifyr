from app.definition._service import Service,BaseService
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.database_service import MongooseService, RedisService
from app.services.email_service import EmailSenderService
from app.services.webhook_service import WebhookService

@Service()
class WorkflowService(BaseService):

    def __init__(self,configService:ConfigService,mongooseService:MongooseService,redisService:RedisService,
                webhookService:WebhookService,emailSenderService:EmailSenderService,contactService:ContactsService,llmService:LLMService):
        super().__init__()
        self.configService = configService
        self.mongooseService = mongooseService
        self.redisService = redisService
        self.webhookService = webhookService
        self.emailSenderService = emailSenderService
        self.contactService = contactService