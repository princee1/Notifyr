from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseServiceLock
from app.services.database_service import MongooseService, TortoiseConnectionService
from app.services.secret_service import HCVaultService
from app.container import Get, InjectInMethod
from app.services.security_service import JWTAuthService


@HTTPRessource('message')
class CRUDSecretMessageRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,vaultService:HCVaultService,jwtAuthService:JWTAuthService):
        super().__init__()
        self.vaultService = vaultService
        self.jwtAuthService = jwtAuthService

    
    def add_message(self):
        ...

    def delete_message(self):
        ...
    
    def read_message(self):
        ...
    
    def modify_message(self):
        ...


@HTTPRessource('vault')
class SecretMessageRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,vaultService:HCVaultService,mongooseService:MongooseService,tortoiseConnectionService:TortoiseConnectionService):
        super().__init__()
        self.vaultService =vaultService
        self.mongooseService = mongooseService
        self.tortoiseConnectionService = tortoiseConnectionService

        self.jwtService = Get(JWTAuthService)
    

    @UseServiceLock(HCVaultService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET],deprecated=True)
    async def print_creds(self,):
        ...

    
    async def encrypt_message(self):
        ...

    async def decrypt_message(self):
        ...
    
    async def verify_message(self):
        ...

    async def sign_message(self):
        ... 

