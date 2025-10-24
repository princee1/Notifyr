from app.definition._error import BaseError
from app.utils.constant import VaultConstant
from app.utils.helper import b64_decode, b64_encode
from hvac import Client
from typing import Literal, TypedDict, Optional, Dict, Any


class VaultDatabaseCredentialsData(TypedDict):
    username: str
    password: str

class VaultDatabaseCredentials(TypedDict, total=False):
    request_id: str
    lease_id: str
    lease_duration: int
    renewable: bool
    data: VaultDatabaseCredentialsData
    wrap_info: Optional[Dict[str, Any]]
    warnings: Optional[list[str]]
    auth: Optional[Dict[str, Any]]


# Hash / HMAC / Signing algorithms
HASH_ALGORITHMS = [
    "sha2-224",
    "sha2-256",
    "sha2-384",
    "sha2-512",
]

# Signature-capable key types
SIGNING_KEY_TYPES = [
    "ed25519",
    "ecdsa-p256",
    "ecdsa-p384",
    "ecdsa-p521",
    "rsa-2048",
    "rsa-3072",
    "rsa-4096",
]

# Extra options (used as parameters for specific keys)
RSA_SIGNATURE_ALGORITHMS = ["pss", "pkcs1v15"]
ECDSA_MARSHALING_ALGORITHMS = ["asn1", "jws"]
RSA_PSS_SALT_LENGTHS = ["auto", "hash"]  # or an integer within allowed range

ROLE_PREFIX= '-ntfr-role'

class VaultError(BaseError):
    ...



class VaultEngine:
    def __init__(self,client:Client,mount_point:str):
        self.client = client
        self.mount_point = mount_point

class KV1VaultEngine(VaultEngine):
    
    def read(self, sub_mount: VaultConstant.NotifyrSecretType, path: str = '', wrap_response: bool = False, wrap_ttl: str = "60s",data_only=True,wrap_token_only=True):
        params = {
            "path": VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            "mount_point": self.mount_point,
        }
        if wrap_response:
            params["wrap_ttl"] = wrap_ttl
        read_response = self.client.secrets.kv.v1.read_secret(**params)
        print("KV Read:", read_response)

        if wrap_token_only and wrap_response:
            if wrap_response and 'wrap_info' in read_response:
                return {"wrap_token": read_response['wrap_info']['token']}
    
        elif data_only:
            if 'data' in read_response:
                return read_response['data']
            
        return read_response

    def put(self, sub_mount: VaultConstant.NotifyrSecretType, data: dict, path: str = ''):
        params = {
            "path": VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            "secret": data,
            "mount_point": self.mount_point,
        }
        write_response = self.client.secrets.kv.v1.create_or_update_secret(**params)
        return write_response
    
    def delete(self,sub_mount:VaultConstant.NotifyrSecretType,path:str):
        delete_response = self.client.secrets.kv.v1.delete_secret(
            path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
            mount_point=self.mount_point
                )    
        return delete_response

class KV2VaultEngine(VaultEngine):

    def read(self, sub_mount: VaultConstant.NotifyrSecretType, path: str = '', version: int = None):
        params = {
            "path": VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            "mount_point": self.mount_point,
        }
        if version is not None:
            params["version"] = version
        
        read_response = self.client.secrets.kv.v2.read_secret_version(**params)
        print("KV2 Read:", read_response)
        if 'data' in read_response:
            return read_response['data']
        return {}

    def put(self, sub_mount: VaultConstant.NotifyrSecretType, data: dict, path: str = ''):
        params = {
            "path": VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            "secret": data,
            "mount_point": self.mount_point,
        }
        write_response = self.client.secrets.kv.v2.create_or_update_secret(**params)
        print("KV2 Write:", write_response)
        return write_response

    def undelete(self, sub_mount: VaultConstant.NotifyrSecretType, path: str, versions: list):
        if not versions:
            raise ValueError("You must specify at least one version to undelete.")

        undelete_response = self.client.secrets.kv.v2.undelete_versions(
            path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            versions=versions,
            mount_point=self.mount_point
        )

        print("KV2 Undelete:", undelete_response)
        return undelete_response

    def delete(self, sub_mount: VaultConstant.NotifyrSecretType, path: str, versions: list = []):
        if versions:
            # Soft delete specific versions
            delete_response = self.client.secrets.kv.v2.delete_versions(
                path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
                versions=versions,
                mount_point=self.mount_point
            )
        else:
            # Soft delete latest version
            delete_response = self.client.secrets.kv.v2.delete_latest_version_of_secret(
                path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
                mount_point=self.mount_point
            )
        print("KV2 Delete:", delete_response)
        return delete_response

    def destroy(self, sub_mount: VaultConstant.NotifyrSecretType, path: str, versions: list):
        destroy_response = self.client.secrets.kv.v2.destroy_secret_versions(
            path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            versions=versions,
            mount_point=self.mount_point
        )
        print("KV2 Destroy:", destroy_response)
        return destroy_response

    def rollback(self, sub_mount: VaultConstant.NotifyrSecretType, path: str, version: int,other_version_to_delete:list[int]=[], destroy=False,delete=False):
        # Rollback by reading the old version and writing it as the latest
        old_data = self.read(sub_mount, path, version=version)
        if not old_data:
            if not self.undelete(sub_mount,path, versions=[version]):
                raise ValueError(f"No data found at version {version} for path {path}")
            else:
                old_data = self.read(sub_mount, path, version=version)

        self.put(sub_mount, old_data, path)
        if destroy and other_version_to_delete:
            self.destroy(sub_mount,path,other_version_to_delete)
            return
        if delete and other_version_to_delete:
            self.delete(sub_mount,path,other_version_to_delete)
       
class TransitVaultEngine(VaultEngine):
    
    def encrypt(self, plaintext: str, key: VaultConstant.NotifyrTransitKeyType,ciphertext_only=True):
        encoded_text = b64_encode(plaintext)
        encrypt_response = self.client.secrets.transit.encrypt_data(
            name=key,
            plaintext=encoded_text,
            mount_point=self.mount_point
        )
        if ciphertext_only:
            return encrypt_response['data']['ciphertext']
        return encrypt_response
    
    def decrypt(self, ciphertext: str, key: VaultConstant.NotifyrTransitKeyType,plaintext_only=True):
        decrypted_response = self.client.secrets.transit.decrypt_data(
            name=key,
            ciphertext=ciphertext,
            mount_point=self.mount_point
        )
        if plaintext_only:
            encoded_response = decrypted_response['data']['plaintext']
            return b64_decode(encoded_response)
        return decrypted_response

    def sign(self, input_data: str, key: VaultConstant.NotifyrTransitKeyType, algorithm: str = "sha2-256",signature_only:bool=True) -> str:
        """Signs the given input using Vault transit engine."""
        encoded_input = b64_encode(input_data)
        sign_response = self.client.secrets.transit.sign_data(
            name=key,
            input=encoded_input,
            hash_algorithm=algorithm,
            mount_point=self.mount_point
        )
        print("Sign response:", sign_response)
        if signature_only:
            return sign_response["data"]["signature"]
        return sign_response

    def verify_signature(self, input_data: str, signature: str, key: VaultConstant.NotifyrTransitKeyType, algorithm: str = "sha2-256",valid_only:bool = True) -> bool:
        """Verifies the given signature against input using Vault transit engine."""
        encoded_input = b64_encode(input_data)
        verify_response = self.client.secrets.transit.verify_signed_data(
            name=key,
            input=encoded_input,
            signature=signature,
            hash_algorithm=algorithm,
            mount_point=self.mount_point
        )
        print("Verify response:", verify_response)
        if valid_only:
            return verify_response["data"]["valid"]
        return verify_response

class DatabaseVaultEngine(VaultEngine):

    def generate_credentials(self,role:VaultConstant.NotifyrDynamicSecretsRole)->VaultDatabaseCredentials:
        role+=ROLE_PREFIX
        credentials = self.client.secrets.database.generate_credentials(
            name=role,
            mount_point=self.mount_point
            )
        return VaultDatabaseCredentials(**credentials)
    
class MinioS3VaultEngine(VaultEngine):


    def generate_sts_credentials(self,role_name='static-minio'):
        role_name += ROLE_PREFIX
        
        return self.client.adapter.get(f"/v1/{self.mount_point}/creds/{role_name}")
    
    def generate_static_credentials(self,role_name:str='sts-minio',ttl_seconds=3600):
        role_name += ROLE_PREFIX
        ttl = {"ttl": f"{ttl_seconds}s"} if ttl_seconds and ttl_seconds >=120 else {}

        return self.client.adapter.post(f"/v1/{self.mount_point}/sts/{role_name}", json=ttl )

        
   
    
class AwsEngine(VaultEngine):
    """ AWS Vault Engine for generating dynamic AWS credentials.
    """

