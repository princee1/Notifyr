from app.utils.constant import VaultConstant
from app.utils.helper import b64_decode, b64_encode
from hvac import Client


class VaultEngine:
    def __init__(self,client:Client):
        self.client = client

class KV1VaultEngine(VaultEngine):
    
    def read(self,sub_mount:VaultConstant.NotifyrSecretType,path:str=''):
        read_response = self.client.secrets.kv.v1.read_secret(
        path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
        mount_point=VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,
        )
        print("KV put:",read_response)
        if 'data' in read_response:
            return read_response['data']
        return {}

    def put(self,sub_mount:VaultConstant.NotifyrSecretType,data:dict,path:str=''):
        write_response = self.client.secrets.kv.v1.create_or_update_secret(
        path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
        secret=data,
        mount_point=VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT,)

        print("KV Write:",write_response)
    
    def delete(self,sub_mount:VaultConstant.NotifyrSecretType,path:str):
        delete_response = self.client.secrets.kv.v1.delete_secret(
            path=VaultConstant.KV_ENGINE_BASE_PATH(sub_mount,path),
            mount_point=VaultConstant.NOTIFYR_SECRETS_MOUNT_POINT
                )
        print(delete_response)


class KV2VaultEngine(VaultEngine):
    ...

class TransitVaultEngine(VaultEngine):
    
    
    def encrypt(self,plaintext:str,key:VaultConstant.NotifyrTransitKeyType):
        encoded_text = b64_encode(plaintext)
        encrypt_response = self.client.secrets.transit.encrypt_data(
            name=key,
            plaintext=encoded_text,
            mount_point=VaultConstant.NOTIFYR_TRANSIT_MOUNTPOINT
        )
        print("Encrypted:", encrypt_response)
        return encrypt_response["data"]["ciphertext"]
    
    def decrypt(self,ciphertext:str,key:VaultConstant.NotifyrTransitKeyType):
        decrypted_response = self.client.secrets.transit.decrypt_data(
            name=key,
            ciphertext=ciphertext,
            mount_point=VaultConstant.NOTIFYR_TRANSIT_MOUNTPOINT
        )
        print("Decrypted:",decrypted_response)
        encoded_response = decrypted_response['data']['plaintext']
        return b64_decode(encoded_response)
    

class DatabaseVaultEngine(VaultEngine):
    ...
