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
    lease_id: str
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


class VaultError(BaseError):
    ...



class VaultEngine:
    def __init__(self,client:Client,mount_point:str):
        self.client = client
        self.mount_point = mount_point

class KV1VaultEngine(VaultEngine):
    
    def read(self, sub_mount: VaultConstant.NotifyrSecretType, path: str = '', wrap_response: bool = False, wrap_ttl: str = "60s"):
        params = {
            "path": VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            "mount_point": self.mount_point,
        }
        if wrap_response:
            params["wrap_ttl"] = wrap_ttl
        read_response = self.client.secrets.kv.v1.read_secret(**params)
        print("KV Read:", read_response)
        if wrap_response and 'wrap_info' in read_response:
            return {"wrap_token": read_response['wrap_info']['token']}
        if 'data' in read_response:
            return read_response['data']
        return {}

    def put(self, sub_mount: VaultConstant.NotifyrSecretType, data: dict, path: str = '', wrap_response: bool = False, wrap_ttl: str = "60s"):
        params = {
            "path": VaultConstant.KV_ENGINE_BASE_PATH(sub_mount, path),
            "secret": data,
            "mount_point": self.mount_point,
        }
        if wrap_response:
            params["wrap_ttl"] = wrap_ttl
        write_response = self.client.secrets.kv.v1.create_or_update_secret(**params)
        print("KV Write:", write_response)
        if wrap_response and 'wrap_info' in write_response:
            return {"wrap_token": write_response['wrap_info']['token']}
        return write_response
    
    def delete(self,sub_mount:VaultConstant.NotifyrSecretType,path:str):
        delete_response = self.client.secrets.kv.v1.delete_secret(
            path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
            mount_point=self.mount_point
                )
        print(delete_response)


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
    
    def encrypt(self, plaintext: str, key: VaultConstant.NotifyrTransitKeyType):
        encoded_text = b64_encode(plaintext)
        encrypt_response = self.client.secrets.transit.encrypt_data(
            name=key,
            plaintext=encoded_text,
            mount_point=self.mount_point
        )
        print("Encrypted:", encrypt_response)
        return encrypt_response["data"]["ciphertext"]
    
    def decrypt(self, ciphertext: str, key: VaultConstant.NotifyrTransitKeyType):
        decrypted_response = self.client.secrets.transit.decrypt_data(
            name=key,
            ciphertext=ciphertext,
            mount_point=self.mount_point
        )
        print("Decrypted:", decrypted_response)
        encoded_response = decrypted_response['data']['plaintext']
        return b64_decode(encoded_response)

    def sign(self, input_data: str, key: VaultConstant.NotifyrTransitKeyType, algorithm: str = "sha2-256") -> str:
        """Signs the given input using Vault transit engine."""
        encoded_input = b64_encode(input_data)
        sign_response = self.client.secrets.transit.sign_data(
            name=key,
            input=encoded_input,
            hash_algorithm=algorithm,
            mount_point=self.mount_point
        )
        print("Sign response:", sign_response)
        return sign_response["data"]["signature"]

    def verify_signature(self, input_data: str, signature: str, key: VaultConstant.NotifyrTransitKeyType, algorithm: str = "sha2-256") -> bool:
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
        return verify_response["data"]["valid"]

    

class DatabaseVaultEngine(VaultEngine):

    _role_prefix= '-ntfr-role'

    def generate_credentials(self,role:VaultConstant.NotifyrDynamicSecretsRole)->VaultDatabaseCredentials:
        role+=self._role_prefix
        credentialss = self.client.secrets.database.generate_credentials(
            name=role,
            mount_point=self.mount_point
            )
        return VaultDatabaseCredentials(**credentialss)
    
