import os
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import overload

# ——— Helpers for password-based symmetric encryption ———

def _derive_key(password: bytes, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(password)

def _encrypt_bytes(plaintext: bytes, password: bytes) -> bytes:
    """Return salt(16) || nonce(12) || ciphertext."""
    salt = os.urandom(16)
    key  = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce  = os.urandom(12)
    ct     = aesgcm.encrypt(nonce, plaintext, None)
    return salt + nonce + ct

def _decrypt_bytes(blob: bytes, password: bytes) -> bytes:
    salt, nonce, ct = blob[:16], blob[16:28], blob[28:]
    key = _derive_key(password, salt)
    return AESGCM(key).decrypt(nonce, ct, None)

# ——— Core routines (all in-memory) ———

class RSA:

    # @overload
    # def __init__(self,password:str,key_size:int=2048):
    #     """
    #     """
    #     ...

    # @overload
    # def __init__(public_key:str=None,private_key:str=None):
    #     """
    #     """
    #     ...
        
    def __init__(self,password:str,key_size:int=2048,public_key:bytes=None,private_key:bytes=None):
        self.password= password.encode()
        
        if public_key or private_key:
            if public_key:
                self.encrypted_public_key = public_key
                self.public_key = self.load_public_key_from_bytes(public_key)

            if private_key:
                self.private_key = private_key
                self.private_key = self.load_private_key_from_bytes(private_key)
        else:   
            self.key_size = key_size
            self.encrypted_private_key, self.encrypted_public_key = self.generate_keypair_and_encrypt()
            self.private_key = self.load_private_key_from_bytes(self.encrypted_private_key)
            self.public_key = self.load_public_key_from_bytes(self.encrypted_public_key)
        
    def generate_keypair_and_encrypt(self,):
        """
        Generates an RSA key pair and returns:
        - encrypted_private_pem: bytes, PEM format encrypted with BestAvailableEncryption
        - encrypted_public_pem:  bytes, PEM-like block encrypted with AES-GCM+PBKDF2
        """
        # 1) Generate private key
        priv_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size
        )

        # 2) Serialize/encrypt private key (PEM + PBKDF2→AES-256)
        encrypted_private_pem = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(self.password)
        )

        # 3) Serialize public key (plain PEM)
        public_pem = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # 4) Symmetrically encrypt the public PEM
        blob = _encrypt_bytes(public_pem, self.password)
        b64 = base64.encodebytes(blob).decode('ascii')
        lines = ["-----BEGIN ENCRYPTED PUBLIC KEY-----"]
        lines += [b64[i:i+64] for i in range(0, len(b64), 64)]
        lines.append("-----END ENCRYPTED PUBLIC KEY-----\n")
        encrypted_public_pem = ("\n".join(lines)).encode('ascii')

        return encrypted_private_pem, encrypted_public_pem

    def load_private_key_from_bytes(self,encrypted_private_pem: bytes):
        """
        Decrypts the private key PEM and returns a cryptography RSA private key.
        """
        return serialization.load_pem_private_key(
            encrypted_private_pem,
            password=self.password
        )

    def load_public_key_from_bytes(self,encrypted_public_pem: bytes,):
        """
        Decrypts our PEM-like encrypted public key and returns a RSA public key.
        """
        text = encrypted_public_pem.decode('ascii').strip().splitlines()
        b64 = "".join(text[1:-1])
        blob = base64.decodebytes(b64.encode('ascii'))
        public_pem = _decrypt_bytes(blob,self.password)
        return serialization.load_pem_public_key(public_pem)

    def sign_message(self, message: str) -> bytes:
        """
        Signs a message using the private key.
        """
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature

    def verify_signature(self, message: str, signature: bytes) -> bool:
        """
        Verifies a signature using the public key.
        """
        try:
            self.public_key.verify(
                signature,
                message.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    def encrypt_message(self, message: str) -> bytes:
        """
        Encrypts a message using the public key.
        """
        ciphertext = self.public_key.encrypt(
            message.encode('utf-8'),
            rsa.padding.OAEP(
                mgf=rsa.padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return ciphertext

    def decrypt_message(self, ciphertext: bytes) -> str:
        """
        Decrypts a ciphertext using the private key.
        """
        plaintext = self.private_key.decrypt(
            ciphertext,
            rsa.padding.OAEP(
                mgf=rsa.padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext.decode('utf-8')