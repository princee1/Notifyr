from os import urandom
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.utils.helper import flatten_dict, unflattened_dict
from app.utils.tools import Time

class SecretsWrapper:

    _allowed_type = {dict,str}
    _nonce_index = 4

    def __init__(self, plain_data:dict|str):
        self.plain_type = type(plain_data)
        if self.plain_type not in self._allowed_type:
            raise TypeError('Must be a dict or str')

        self._create_chacha20()
        self.cipher_data:str|dict[str,bytes] = None
        self._encrypt(plain_data)
    
    def _encrypt(self,plain_data:dict|str):
        if self.plain_type == str:
            plain_data = plain_data.encode()
            self.cipher_data = self.encryptor.update(plain_data)
        else:
            self.cipher_data = {}
            #plain_data = flatten_dict(plain_data)
            for k,v in plain_data.items():
                if not isinstance(v,str):
                    continue
                self.cipher_data[k] = self.encryptor.update(v.encode())

    @Time
    def _decrypt(self):
        if self.plain_type == str:
            return self.decryptor.update(self.cipher_data)
        temp_plain = {}
        #temp_plain = unflattened_dict(self.cipher_data)
        for k,v in self.cipher_data.items():
            temp_plain[k] = self.decryptor.update(v.decode())

        return temp_plain

    def _create_chacha20(self):
        key = urandom(32) 
        nonce = urandom(16)

        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)

        self.encryptor = cipher.encryptor()
        self.decryptor = cipher.decryptor()


    @property
    def plain(self)->dict|str:
        return self._decrypt()