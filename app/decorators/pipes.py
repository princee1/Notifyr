from app.classes.auth_permission import AuthPermission
from app.classes.celery import SchedulerModel,CeleryTaskNameNotExistsError,CelerySchedulerOptionError,SCHEDULER_VALID_KEYS
from app.container import InjectInMethod
#from app.services.celery_service import CeleryService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe
from app.task import CeleryService, task_name

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

        return {'tokens':temp}



class CeleryTaskPipe(Pipe):
    @InjectInMethod
    def __init__(self,celeryService:CeleryService):
        super().__init__(True)
        self.celeryService = celeryService
    
    def pipe(self,scheduler:SchedulerModel):
        scheduler.task_name = task_name(scheduler.task_name)
        
        if scheduler.task_type != 'now' and scheduler.task_type != 'once':
            rules_keys = SCHEDULER_VALID_KEYS[scheduler.task_type]
            s_keys = set(scheduler.task_option.keys())
            if len(s_keys) == 0:
                raise CelerySchedulerOptionError
            if len(s_keys.difference(rules_keys)) != 0:
                raise CelerySchedulerOptionError
            
        return {'scheduler':scheduler}