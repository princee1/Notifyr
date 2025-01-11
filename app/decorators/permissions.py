from definition._utils_decorator import Permission
from container import InjectInMethod
from services.security_service import SecurityService,JWTAuthService
from classes.permission import RoutePermission

class JWTAuthPermission(Permission):
    
    @InjectInMethod
    def __init__(self,jwtAuthService: JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
    
    def permission(self, token_:str, client_ip_:str, class_name:str, func_name:str):
        return self.jwtAuthService.verify_permission(token_, class_name, func_name,client_ip_)
    

class JWTRessourcePermission(Permission):
    ...

