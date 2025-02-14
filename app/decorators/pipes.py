from typing import Literal
from app.classes.auth_permission import AuthPermission, TokensModel
from app.classes.celery import SchedulerModel,CelerySchedulerOptionError,SCHEDULER_VALID_KEYS
from app.classes.template import TemplateNotFoundError
from app.container import Get, InjectInMethod
from app.services.assets_service import AssetService, RouteAssetType, DIRECTORY_SEPARATOR, REQUEST_DIRECTORY_SEPARATOR
from app.services.config_service import ConfigService
from app.services.security_service import JWTAuthService
from app.definition._utils_decorator import Pipe
from app.services.celery_service import CeleryService, task_name

class AuthPermissionPipe(Pipe):

    @InjectInMethod
    def __init__(self,jwtAuthService:JWTAuthService):
        super().__init__(True)
        self.jwtAuthService = jwtAuthService

    def pipe(self,tokens:TokensModel):
        tokens = tokens.model_dump(include={'tokens'})
        if isinstance(tokens,str):
            tokens = [tokens]
        temp = {}
        for token in tokens:
            val = self.jwtAuthService.decode_token(token)
            permission:AuthPermission = AuthPermission(**val)
            temp[permission.issued_for] = permission

        return {'tokens':temp}

class TemplateParamsPipe(Pipe):
    
    def __init__(self,template_type:RouteAssetType):
        super().__init__(True)
        self.assetService= Get(AssetService)
        self.configService = Get(ConfigService)
        self.template_type = template_type
    
    def pipe(self,template:str):
        asset_routes = self.assetService.exportRouteName(self.template_type)
        template = template.replace(REQUEST_DIRECTORY_SEPARATOR,DIRECTORY_SEPARATOR)
        template = self.assetService.asset_rel_path(template,self.template_type)

        if template not in asset_routes:
            raise TemplateNotFoundError(template)

        return {'template':template}
        

class CeleryTaskPipe(Pipe):
    
    def __init__(self):
        super().__init__(True)
        self.celeryService = Get(CeleryService)
    
    def pipe(self,scheduler:SchedulerModel):
        scheduler.task_name = task_name(scheduler.task_name)
        
        if scheduler.task_type != 'now' and scheduler.task_type != 'once':
            rules_keys = SCHEDULER_VALID_KEYS[scheduler.task_type]
            s_keys = set(scheduler.task_option.keys())
            if len(s_keys) == 0:
                raise CelerySchedulerOptionError
            if len(s_keys.difference(rules_keys)) != 0:
                raise CelerySchedulerOptionError
        
        setattr(scheduler,'heaviness' , self.celeryService._task_registry[scheduler.task_name]['heaviness'])
        return {'scheduler':scheduler}