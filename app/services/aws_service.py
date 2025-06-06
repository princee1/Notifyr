from app.definition._service import BaseService, Service
from .config_service import ConfigService
from .file_service import BaseFileRetrieverService, FileService
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import List, Dict


@Service
class AmazonS3Service(BaseFileRetrieverService):
    
    def __init__(self,configService:ConfigService,fileService:FileService) -> None:
        super().__init__(configService,fileService)

class AmazonSESError(Exception):
    pass


class AmazonSNSError(Exception):
    pass

@Service
class AmazonSESService(BaseService):
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService
    
    def build(self):
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

@Service
class AmazonSNSService(BaseService):
    def __init__(self, configService: ConfigService) -> None:
        super().__init__()
        self.configService = configService

    def build(self):
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
