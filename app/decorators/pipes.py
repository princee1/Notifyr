from app.classes.auth_permission import AuthPermission
from app.container import InjectInMethod
from app.services.celery_service import CeleryService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe

class AuthPermissionPipe(Pipe):

    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__(True)
        self.jwtAuthService = jwtAuthService

    def pipe(self,tokens:str| list[str]):
        if isinstance(tokens,str):
            tokens = [tokens]
        temp = {}
        for token in tokens:
            val = self.jwtAuthService.decode_token(token)
            permission:AuthPermission = AuthPermission(**val)
            temp[permission.issued_for] = permission

        return (),{'tokens':temp}


class CeleryTaskIdentifierPipe(Pipe):

    @InjectInMethod
    def __init__(self, celeryService:CeleryService):
        super().__init__(True)
        self.celeryService:CeleryService = celeryService
    
    def pipe(self,task_id:str):
        return self.celeryService.get_task_id(task_id)