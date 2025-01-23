from classes.permission import AuthPermission
from services.security_service import JWTAuthService
from definition._utils_decorator import Pipe

class AuthPermissionPipe(Pipe):

    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__(True)
        self.jwtAuthService = jwtAuthService

    def pipe(self,tokens:str| list[str]):
        if isinstance(tokens,str):
            tokens = [tokens]
        temp = {}
        for token in tokens:
            val = self.jwtAuthService._decode_auth_token(token)
            permission:AuthPermission = AuthPermission(**val)
            temp[permission.issued_for] = permission

        return (),{'tokens':temp}
