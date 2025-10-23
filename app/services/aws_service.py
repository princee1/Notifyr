from datetime import timedelta
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.commonconfig import CopySource
from app.classes.vault_engine import VaultDatabaseCredentials, VaultDatabaseCredentialsData
from app.definition._error import BaseError
from app.definition._service import DEFAULT_BUILD_STATE, BaseMiniService, BaseService, LinkDep, MiniService, Service
from app.interface.timers import SchedulerInterface
from app.interface.email import EmailInterface, EmailReadInterface, EmailSendInterface
from app.models.profile_model import AWSProfileModel
from app.services.profile_service import ProfileMiniService, ProfileService
from app.services.secret_service import HCVaultService
from app.utils.constant import MinioConstant, VaultConstant, VaultTTLSyncConstant
from .config_service import ConfigService
from .file_service import BaseFileRetrieverService, FileService
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import List, Dict
from app.services.database_service import RotateCredentialsInterface


class AmazonS3ServiceError(BaseError):
    pass

class ObjectNotFoundError(AmazonS3ServiceError):
    pass

class AmazonSESError(Exception):
    pass


class AmazonSNSError(Exception):
    pass


@Service(

)
class AmazonS3Service(BaseFileRetrieverService,RotateCredentialsInterface):
    
    def __init__(self,configService:ConfigService,fileService:FileService,vaultService:HCVaultService) -> None:
        super().__init__(configService,fileService)
        RotateCredentialsInterface.__init__(self,vaultService,VaultTTLSyncConstant.MINIO_TTL)
        self.STORAGE_METHOD = 'mount(same FS)','s3 object storage(source of truth)'
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        self.client_init()
        
    def _creds_rotator(self):
        self.client_init()        

    def client_init(self,):
        if self.configService.MINIO_CRED_TYPE == 'static':
            creds = self.vaultService.minio_engine.generate_static_credentials(ttl_seconds=VaultTTLSyncConstant.MINIO_TTL)
        else:
            creds = self.vaultService.minio_engine.generate_sts_credentials()

        self.creds = VaultDatabaseCredentials(request_id=creds['request_id'], lease_id=creds["lease_id"], lease_duration=creds["lease_duration"],
            renewable=creds["renewable"], wrap_info=creds.get("wrap_info", None), data=VaultDatabaseCredentialsData(
                username=creds['data']['accessKeyId'],
                password=creds['data']['secretAccessKey']
            ), 
            auth=creds.get('auth', None), warnings=creds.get('warnings', None)
        )

        self.client = Minio(
            endpoint=self.configService.MINIO_ENDPOINT,
            access_key=self.db_user,
            secret_key=self.db_password,
            secure=self.configService.MINIO_SSL,
            region=self.configService.MINIO_REGION
        )

    def delete_object(self,object_name: str,version_id: str = None):
        _object = self.get_object(object_name,version_id)
        self.client.remove_object(MinioConstant.TEMPLATE_BUCKET, object_name, version_id=version_id)
        return _object

    def delete_prefix(self, prefix: str,recursive: bool = True):
        objects = self.client.list_objects(MinioConstant.TEMPLATE_BUCKET, prefix=prefix, recursive=recursive)
        if objects:
            self.client.remove_objects(MinioConstant.TEMPLATE_BUCKET, [DeleteObject(obj.object_name) for obj in objects])
        error = self.client.remove_objects(MinioConstant.TEMPLATE_BUCKET, [DeleteObject(obj.object_name) for obj in objects])
        if error:
            print(error)
        # Alternatively, if you want to delete all objects under the prefix without using remove_objects
        # for obj in objects:
        #     self.client.remove_object(MinioConstant.TEMPLATE_BUCKET, obj.object_name)

    def get_object(self,object_name: str,version_id: str = None):
        _object = self.client.get_object(MinioConstant.TEMPLATE_BUCKET, object_name, version_id=version_id)  
        if _object.status != 200:
            raise ObjectNotFoundError(f'Object {object_name} not found in bucket {MinioConstant.TEMPLATE_BUCKET}')
        return _object
    
    def list_objects(self,prefix: str='',recursive: bool = True):
        objects = self.client.list_objects(MinioConstant.TEMPLATE_BUCKET, prefix=prefix, recursive=recursive)
        return objects

    def move_object(self,source_object_name: str,dest_object_name: str,version_id: str = None):
        self.get_object(source_object_name,version_id)
        self.client.copy_object(
            MinioConstant.TEMPLATE_BUCKET,
            dest_object_name,
            source=CopySource(bucket=MinioConstant.TEMPLATE_BUCKET, object=source_object_name, version_id=version_id)
        )
        self.client.remove_object(MinioConstant.TEMPLATE_BUCKET, source_object_name, version_id=version_id)
        return self.get_object(dest_object_name)
    
    def upload_object(self,object_name: str,data, content_type: str = 'application/octet-stream'):
        result = self.client.put_object(
            MinioConstant.TEMPLATE_BUCKET,object_name,data,len(data),content_type=content_type
        )
        return self.get_object(object_name)
    
    def download_object(self,object_name: str,version_id: str = None):
        _object = self.get_object(object_name,version_id)
        return _object.read()

    def download_prefix(self,prefix: str,recursive: bool = True):
        objects = self.client.list_objects(MinioConstant.TEMPLATE_BUCKET, prefix=prefix, recursive=recursive)
        downloaded_objects = {}
        for obj in objects:
            downloaded_objects[obj.object_name] = self.download_object(obj.object_name)
        return downloaded_objects
    
    def generate_presigned_url(self,object_name: str,expiry: int = 3600,method: str = 'GET',version_id: str = None):
        url = self.client.presigned_get_object(
            MinioConstant.TEMPLATE_BUCKET,
            object_name,
            version_id=version_id,
            expires=timedelta(seconds=expiry)
        ) if method == 'GET' else self.client.presigned_put_object(
            MinioConstant.TEMPLATE_BUCKET,
            object_name,
            expires=timedelta(seconds=expiry)
        )
        return url
@MiniService(
    links=[LinkDep(ProfileMiniService,to_destroy=True, to_build=True)]
)
class AmazonSESService(BaseMiniService):
    def __init__(self, configService: ConfigService,profileMiniService:ProfileMiniService[AWSProfileModel]) -> None:
        self.depService = profileMiniService
        super().__init__(profileMiniService,None)
        EmailSendInterface.__init__(self,None)
        EmailReadInterface.__init__(self,None)
        EmailInterface.__init__(self,self.depService.model.email_address)
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
