from definition._utils_decorator import Permission
from container import InjectInMethod
from services.security_service import SecurityService,JWTAuthService
from classes.permission import RoutePermission

class JWTAuthPermission(Permission):
    
    @InjectInMethod
    def __init__(self,jwtAuthService: JWTAuthService):
        super().__init__()
        self.jwtAuthService = jwtAuthService
    
    def permission(self, token_, issued_for, class_name, func_name):
        return self.jwtAuthService.verify_permission(token_, class_name, func_name,issued_for)
    

class JWTRessourcePermission(Permission):
    ...

