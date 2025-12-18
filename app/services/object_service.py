from datetime import timedelta
from minio import Minio
from minio.helpers import ObjectWriteResult
from minio.datatypes import Object
from minio.deleteobjects import DeleteObject,DeleteError
from minio.commonconfig import CopySource
from minio.error import S3Error,ServerError, InvalidResponseError, MinioAdminException
from app.classes.vault_engine import VaultDatabaseCredentials, VaultDatabaseCredentialsData
from app.definition._error import BaseError
from app.definition._service import DEFAULT_BUILD_STATE, GUNICORN_BUILD_STATE, BaseMiniService, BaseService, LinkDep, MiniService, Service
from app.errors.service_error import BuildFailureError
from app.services.database.base_db_service import TempCredentialsDatabaseService
from app.services.file.base_file_fetcher_service import BaseFileRetrieverService
from app.services.file.file_service import FileService
from app.services.secret_service import HCVaultService
from app.utils.constant import MinioConstant, VaultTTLSyncConstant
from app.utils.tools import RunInThreadPool
from .config_service import  ConfigService
from typing import List, Dict
#from aiobotocore import client


class ObjectNotFoundError(BaseError):
    pass

MINIO_OBJECT_BUILD_STATE = 1001
MINIO_OBJECT_DESTROY_STATE = 1001

@Service(abstract_service_register=[BaseFileRetrieverService])
class AmazonS3Service(TempCredentialsDatabaseService):
    
    def __init__(self,configService:ConfigService,fileService:FileService,vaultService:HCVaultService) -> None:
        TempCredentialsDatabaseService.__init__(self,configService,fileService,vaultService,VaultTTLSyncConstant.MINIO_TTL)
        
        self.STORAGE_METHOD = 'mount(same FS)','s3 object storage(source of truth)'
        self.download_cache = {}
    
    def build(self, build_state = DEFAULT_BUILD_STATE):
        try:
            self.client_init()
            super().build()
        except ServerError as e:
            raise BuildFailureError(f'Failed to build AmazonS3Service due to server error: {str(e)}') from e
        except InvalidResponseError as e:
            raise BuildFailureError(f'Failed to build AmazonS3Service due to invalid response: {str(e)}') from e
        except S3Error as e:
            raise BuildFailureError(f'Failed to build AmazonS3Service: {str(e)}') from e
        except MinioAdminException as e:
            raise BuildFailureError(f'Failed to build AmazonS3Service due to Minio Admin error: {str(e)}') from e
        
        
    async def _creds_rotator(self):
        self.client_init()        

    def client_init(self,):
        if self.configService.S3_CRED_TYPE == 'MINIO':
            self.generate_minio_creds()
        else:
            self.generate_aws_creds()

        self.client = Minio(
            endpoint=self.configService.S3_ENDPOINT,
            access_key=self.db_user,
            secret_key=self.db_password,
            secure=self.configService.MINIO_SSL,
            region=self.configService.S3_REGION
        )
        
    def generate_aws_creds(self):
        ...  # Implementation for generating AWS credentials

    def generate_minio_creds(self):
        if not self.configService.MINIO_STS_ENABLE:
            creds = self.vaultService.minio_engine.generate_static_credentials()
        else:
            creds = self.vaultService.minio_engine.generate_sts_credentials(ttl_seconds=VaultTTLSyncConstant.MINIO_TTL)

        self.creds = VaultDatabaseCredentials(request_id=creds['request_id'], lease_id=creds["lease_id"], lease_duration=creds["lease_duration"],
            renewable=creds["renewable"], wrap_info=creds.get("wrap_info", None), data=VaultDatabaseCredentialsData(
                username=creds['data']['accessKeyId'],
                password=creds['data']['secretAccessKey']
            ), 
            auth=creds.get('auth', None), warnings=creds.get('warnings', None)
        )

    @RunInThreadPool
    async def delete_object(self,object_name: str,version_id: str = None,buckets=MinioConstant.ASSETS_BUCKET):
        _object = await self.stat_objet(object_name,version_id,buckets=buckets)
        self.client.remove_object(buckets, object_name, version_id=version_id)
        return _object

    @RunInThreadPool
    def delete_objects_prefix(self, prefix: str,recursive: bool = True,match:str=None,delete_version=False,objects=None,buckets=MinioConstant.ASSETS_BUCKET):
        if not objects:
            objects = self.list_objects(prefix=prefix, recursive=recursive,match=match,include_version=delete_version,include_delete_marker=False)
        if not objects:
            raise ObjectNotFoundError 
        
        errors = self.client.remove_objects(buckets, [DeleteObject(obj.object_name) for obj in objects])
        return {
            'meta':objects,
            'errors':errors
        }
        # Alternatively, if you want to delete all objects under the prefix without using remove_objects
        # for obj in objects:
        #     self.client.remove_object(MinioConstant.TEMPLATE_BUCKET, obj.object_name)

    def read_object(self,object_name: str,version_id: str = None,buckets=MinioConstant.ASSETS_BUCKET):
        _object = self.client.get_object(buckets, object_name, version_id=version_id)  
        if _object.status != 200:
            raise ObjectNotFoundError(f'Object {object_name} not found in bucket {buckets}')
        return _object
    
    def list_objects(self,prefix: str='',recursive: bool = True,match:str=None,include_version=True,include_delete_marker=True,buckets=MinioConstant.ASSETS_BUCKET):
        objects = self.client.list_objects(buckets, prefix=prefix, recursive=recursive,include_version=include_version)
        return [o for o in objects if (self.fileService.file_matching(o.object_name,match) and not o.is_dir and (include_delete_marker or not o.is_delete_marker))]
    
    @RunInThreadPool
    async def copy_object(self,source_object_name: str,dest_object_name: str,version_id: str = None,move=False,buckets=MinioConstant.ASSETS_BUCKET):
        self.read_object(source_object_name,version_id,buckets).close()
        result = self.client.copy_object(
            buckets,
            dest_object_name,
            source=CopySource(bucket=buckets, object=source_object_name, version_id=version_id)
        )
        
        if move:
            self.client.remove_object(buckets, source_object_name, version_id=version_id)
        meta = await self.stat_objet(dest_object_name,check_existence=True,buckets=buckets)
        return {
            'result':result,
            'meta':meta
        }

    @RunInThreadPool
    def upload_object(self,object_name: str,data:bytes, content_type: str = 'application/octet-stream',metadata: Dict = None,buckets=MinioConstant.ASSETS_BUCKET):
        return self.client.put_object(
            buckets,object_name,data,len(data),content_type=content_type,metadata=metadata
        )
    
    @RunInThreadPool
    def stat_objet(self,object_name,version_id,check_existence:bool=True,buckets=MinioConstant.ASSETS_BUCKET)->Object:
        if check_existence:
            self.read_object(object_name,version_id,buckets).close()
        return self.client.stat_object(
            buckets,object_name,version_id=version_id
        )        
    
    @RunInThreadPool
    def download_objects(self,prefix: str,recursive: bool = True,match:str=None,objects:list[Object]=None,buckets=MinioConstant.ASSETS_BUCKET):
        if objects == None:
            objects = self.list_objects(prefix=prefix, recursive=recursive,match=match,include_version=False,include_delete_marker=False,buckets=buckets)
        downloaded_objects = {}
        if not objects:
            raise ObjectNotFoundError
            
        for obj in objects:
            content =  self.read_object(obj.object_name,buckets=buckets).read()
            if obj.metadata and obj.metadata.get(MinioConstant.ENCRYPTED_KEY,False):
                content = self.vaultService.transit_engine.decrypt(content.decode(),'s3-rest-key',).encode()
            
            downloaded_objects[obj.bucket_name] = content
        return downloaded_objects

    def write_into_disk(self,object_name:str,disk_rel_path:str,buckets=MinioConstant.ASSETS_BUCKET):
        return self.client.fget_object(
                buckets,
                object_name,
                disk_rel_path
            )
        
    @RunInThreadPool
    def generate_presigned_url(self,object_name: str,expiry: int = 3600,method: str = 'GET',version_id: str = None,buckets=MinioConstant.ASSETS_BUCKET):
        url = self.client.presigned_get_object(
            buckets,
            object_name,
            version_id=version_id,
            expires=timedelta(seconds=expiry)
        ) if method == 'GET' else self.client.presigned_put_object(
            buckets,
            object_name,
            expires=timedelta(seconds=expiry)
        )
        return url  

    @property
    def external(self,):
        if self.configService.S3_ENDPOINT == 'minio:9000':
            return False
        addr = self.configService.S3_ENDPOINT.split(':')[0]
        if addr =='localhost':
            return False
        return not addr.startswith('127.0.0')