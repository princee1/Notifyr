from app.definition._service import BaseMiniService, BaseService, LinkDep, MiniService, Service
from app.interface.email import EmailReadInterface, EmailSendInterface
from app.models.profile_model import AWSProfileModel
from app.services.profile_service import ProfileMiniService, ProfileService
from .config_service import ConfigService
from .file_service import BaseFileRetrieverService, FileService
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import List, Dict



class AmazonSESError(Exception):
    pass


class AmazonSNSError(Exception):
    pass


@Service()
class AmazonS3Service(BaseFileRetrieverService):
    
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)

@MiniService(
    override_init=True,
    links=[LinkDep(ProfileMiniService,build_follow_dep=True)]

)
class AmazonSESService(BaseMiniService,EmailSendInterface,EmailReadInterface):
    def __init__(self, configService: ConfigService,profileMiniService:ProfileMiniService[AWSProfileModel]) -> None:
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)
        EmailSendInterface.__init__(self,None)
        EmailReadInterface.__init__(self,None)
        self.email_address = self.depService.model.email_address
        self.configService = configService
    
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
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService

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
