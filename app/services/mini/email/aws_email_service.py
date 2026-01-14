from typing import Dict, List
from app.definition._error import BaseError
from app.definition._service import BaseMiniService, LinkDep, MiniService
from app.interface.email import EmailReadInterface, EmailSendInterface, Mode
from app.models.communication_model import AWSProfileModel
from app.services.config_service import ConfigService
from app.services.profile_service import ProfileMiniService
from botocore.exceptions import BotoCoreError, ClientError
from app.interface.email import EmailReadInterface, EmailSendInterface, Mode
from app.models.communication_model import AWSProfileModel
from app.services.database.redis_service import RedisService
from app.services.profile_service import ProfileMiniService
from app.services.reactive_service import ReactiveService
from app.definition._service import BaseMiniService, BaseService, LinkDep, MiniService, Service



class objectS3ServiceError(BaseError):
    pass

class AmazonSESError(Exception):
    pass


class AmazonSNSError(Exception):
    pass


@MiniService(
    override_init=True,
    links=[LinkDep(ProfileMiniService,to_build=True,to_destroy=True)]
)
class AmazonSESService(BaseMiniService):
    def __init__(self,mode:Mode, profileMiniService:ProfileMiniService[AWSProfileModel], configService: ConfigService,reactiveService:ReactiveService,redisService:RedisService) -> None:
        self.depService = profileMiniService
        self.mode=mode
        super().__init__(profileMiniService,None)
        EmailSendInterface.__init__(self,self.depService.model.email_address)
        EmailReadInterface.__init__(self,self.depService.model.email_address)
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService

    
    def build(self,build_state=-1):
        return super().build()
        
        self.ses_client = boto3.client(
            'ses',
            aws_access_key_id=self.configService['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=self.configService['AWS_SECRET_ACCESS_KEY'],
            region_name=self.configService['AWS_REGION']
        )

    def send_email(self, sender: str, recipients: List[str], subject: str, body: str, body_type: str = "Text") -> Dict:
        try:
            response = self.ses_client.send_email(
                Source=sender,
                Destination={
                    'ToAddresses': recipients
                },
                Message={
                    'Subject': {
                        'Data': subject
                    },
                    'Body': {
                        body_type: {
                            'Data': body
                        }
                    }
                }
            )
            return response
        except (BotoCoreError, ClientError) as e:
            raise AmazonSESError(f"Failed to send email: {e}")

@Service()
class AmazonSNSService(BaseService):
    def __init__(self, configService: ConfigService,reactiveService:ReactiveService,redisService:RedisService) -> None:
        super().__init__()
        self.configService = configService
        self.reactiveService = reactiveService
        self.redisService = redisService

    def build(self,build_state=-1):
        return super().build()
        self.sns_client = boto3.client(
            'sns',
            aws_access_key_id=self.configService['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=self.configService['AWS_SECRET_ACCESS_KEY'],
            region_name=self.configService['AWS_REGION']
        )

    def subscribe_to_ses_events(self, topic_arn: str, protocol: str, endpoint: str) -> Dict:
        try:
            response = self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol=protocol,
                Endpoint=endpoint
            )
            return response
        except (BotoCoreError, ClientError) as e:
            raise AmazonSNSError(f"Failed to subscribe to SES events: {e}")
