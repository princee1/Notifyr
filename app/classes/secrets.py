from os import urandom
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from typing import Union
from app.utils.helper import DICT_SEP, flatten_dict, unflattened_dict
from app.utils.tools import Time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms


class SecretsWrapper:
    
    def __init__(self, plain_data:str|dict[str,str],key=urandom(32),nonce=urandom(16)):
        if not isinstance(plain_data, (str, dict)):
            raise TypeError("plain_data must be str or dict")
        self.plain_type = type(plain_data)
        self.key = key
        self.nonce = nonce
        self.cipher_data:bytes|dict[str,bytes] = None
        self._encrypt(plain_data)
    
    def _encrypt(self,plain_data:str|dict[str,str]):
        ...
    
    def _decrypt(self):
        ...
    
    
    def to_plain(self,sep='/') -> Union[str, dict]:
        """Access decrypted plaintext."""
        return unflattened_dict(self._decrypt(),sep)
        
class ChaCha20SecretsWrapper(SecretsWrapper):
    
    def _new_cipher(self):
        algorithm = algorithms.ChaCha20(self.key, self.nonce)
        return Cipher(algorithm, mode=None)

    def _encrypt(self,plain_data:str|dict[str,str]):
        
        if isinstance(plain_data, str):
            cipher = self._new_cipher()
            encryptor = cipher.encryptor()
            self.cipher_data = encryptor.update(plain_data.encode())
        else:
            self.cipher_data = {}
            for k, v in plain_data.items():
                cipher = self._new_cipher()
                encryptor = cipher.encryptor()
                self.cipher_data[k] = encryptor.update(v.encode())

    @Time
    def _decrypt(self):
        
        if isinstance(self.cipher_data, str):
            cipher = self._new_cipher()
            decryptor = cipher.decryptor()
            return decryptor.update(self.cipher_data).decode()
        else:
            temp_plain = {}
            for k, v in self.cipher_data.items():
                cipher = self._new_cipher()
                decryptor = cipher.decryptor()
                temp_plain[k] = decryptor.update(v).decode()
            return temp_plain
      
class ChaCha20Poly1305SecretsWrapper(SecretsWrapper):
    """
    Secure wrapper around ChaCha20-Poly1305 AEAD encryption.
    Supports both string and dict data.
    Automatically manages nonces and integrity protection.
    """

    def __init__(self, plain_data: Union[str, dict], key: bytes = None):
        key = key or ChaCha20Poly1305.generate_key()
        self.chacha = ChaCha20Poly1305(key)
        super().__init__(plain_data,key,{})

    def _encrypt(self, plain_data: Union[str, dict]):
        """Encrypt the plaintext data."""
        if isinstance(plain_data, str):
            nonce = urandom(12)
            ciphertext = self.chacha.encrypt(nonce, plain_data.encode(), None)
            self.cipher_data = ciphertext
            self.nonce = {"__single__": nonce}
        else:
            self.cipher_data = {}
            for k, v in plain_data.items():
                if not isinstance(v, str):
                    continue
                nonce = urandom(12)
                ciphertext = self.chacha.encrypt(nonce, v.encode(), None)
                self.cipher_data[k] = ciphertext
                self.nonce[k] = nonce
    
    @Time
    def _decrypt(self) -> Union[str, dict]:
        """Decrypt the stored ciphertext."""
        if self.plain_type == str:
            nonce = self.nonce["__single__"]
            plaintext = self.chacha.decrypt(nonce, self.cipher_data, None)
            return plaintext.decode("utf-8")
        else:
            temp_plain = {}
            for k, ciphertext in self.cipher_data.items():
                nonce = self.nonce[k]
                plaintext = self.chacha.decrypt(nonce, ciphertext, None)
                temp_plain[k] = plaintext.decode("utf-8")
            return temp_plain

    
    def export(self) -> dict:
        """Export encrypted data and nonces (for storage or transmission)."""
        return {
            "cipher_data": self.cipher_data,
            "nonces": self.nonce,
            "key": self.key,
        }

    @classmethod
    def from_encrypted(cls, data: dict):
        """
        Restore a SecretsWrapper from exported encrypted data.
        Usage:
            sw = SecretsWrapper.from_encrypted(saved_data)
            print(sw.plain)
        """
        key = data["key"]
        obj = cls.__new__(cls)  # bypass __init__
        obj.key = key
        obj.chacha = ChaCha20Poly1305(key)
        obj.plain_type = str if "__single__" in data["nonces"] else dict
        obj.cipher_data = data["cipher_data"]
        obj.nonce = data["nonces"]
        return obj
