from typing import Annotated
from fastapi import Depends, Request, Response, status
from fastapi.params import Query
from app.classes.auth_permission import Role
from app.container import Get, InjectInMethod
from app.decorators.handlers import AsyncIOHandler, GlobalVarHandler, ServiceAvailabilityHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import GlobalPointerIteratorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, UseServiceLock, UseRoles
from app.definition._service import StateProtocol, ServiceStatus
from app.depends.dependencies import get_auth_permission
from app.errors.properties_error import GlobalKeyDoesNotExistsError
from app.models.properties_model import GlobalVarModel, SettingsModel
from app.services.assets_service import AssetService
from app.depends.class_dep import Broker
from app.services.aws_service import AmazonS3Service
from app.depends.variables import global_var_key, force_update_query, wait_timeout_query
from app.services.config_service import ConfigService
from app.services.database_service import JSONServerDBService
from app.services.file_service import FTPService
from app.services.setting_service import SETTING_SERVICE_ASYNC_BUILD_STATE, DEFAULT_SETTING, SettingService
from app.utils.constant import SettingDBConstant
from app.utils.helper import APIFilterInject, PointerIterator

VARIABLES_ROUTE = 'global'
PARAMS_KEY_SEPARATOR = "@"

GLOBAL_KEY_RAISE = 1
GLOBAL_KEY = 0


@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler, AsyncIOHandler, GlobalVarHandler)
@HTTPRessource(VARIABLES_ROUTE)
class GlobalAssetVariableRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self, configService: ConfigService, assetService: AssetService, awsS3Service: AmazonS3Service, ftpService: FTPService):
        super().__init__(None, None)
        self.assetService = assetService
        self.awsS3Service = awsS3Service
        self.ftpService = ftpService
        self.configService = configService

    @UseLimiter(limit_value='500/minutes')
    @UseServiceLock(AssetService,lockType= 'reader')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UseRoles([Role.PUBLIC])
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET],)
    async def read_global(self, response: Response, request: Request, globalIter: PointerIterator = Depends(global_var_key[GLOBAL_KEY]), wait_timeout: int | float = Depends(wait_timeout_query), authPermission=Depends(get_auth_permission)):

        data = self.assetService.globals.data
        if globalIter == None:
            return data

        ptr = globalIter.ptr(data)
        if ptr == None:
            raise GlobalKeyDoesNotExistsError(
                PARAMS_KEY_SEPARATOR, globalIter.var)

        flag, val = globalIter.get_val(ptr)
        if not flag:
            raise GlobalKeyDoesNotExistsError(
                PARAMS_KEY_SEPARATOR, globalIter.var)

        return {"value": val}

    @UseLimiter(limit_value='10/hours')
    @UseServiceLock(AssetService, lockType='writer')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UseRoles([Role.ADMIN])
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.DELETE],)
    async def delete_global(self, response: Response, request: Request, broker: Annotated[Broker, Depends(Broker)], wait_timeout: int | float = Depends(wait_timeout_query), globalIter: PointerIterator = Depends(global_var_key[GLOBAL_KEY_RAISE]), authPermission=Depends(get_auth_permission)):
        if globalIter == None:
            ...
        else:
            ptr = globalIter.ptr(self.assetService.globals.data)
            if ptr == None:
                raise GlobalKeyDoesNotExistsError(
                    PARAMS_KEY_SEPARATOR, globalIter.var)

            flag, val = globalIter.get_val(ptr)
            if not flag:
                raise GlobalKeyDoesNotExistsError(
                    PARAMS_KEY_SEPARATOR, globalIter.var)

            globalIter.del_val(ptr)
            self.assetService.globals.save()

        broker.propagate_state(StateProtocol(
            service=self.assetService.name, status=ServiceStatus.NOT_AVAILABLE.value, to_build=True, to_destroy=True))
        return {"value": val}

    @UseLimiter(limit_value='10/hours')
    @UseServiceLock(AssetService,lockType= 'writer')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UseRoles([Role.ADMIN])
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.POST, HTTPMethod.PUT],)
    async def upsert_global(self, response: Response, request: Request, broker: Annotated[Broker, Depends(Broker)], globalModel: GlobalVarModel, wait_timeout: int | float = Depends(wait_timeout_query), globalIter: PointerIterator = Depends(global_var_key[GLOBAL_KEY]), force: bool = Depends(force_update_query), authPermission=Depends(get_auth_permission)):

        if globalIter == None:
            ptr = self.assetService.globals.data
        else:
            ptr = globalIter.ptr(self.assetService.globals.data)
            if ptr == None:
                raise GlobalKeyDoesNotExistsError(
                    PARAMS_KEY_SEPARATOR, globalIter.var)

        value = globalModel.model_dump()

        if force:
            ptr.update(value)
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_201_CREATED
            for k, v in value.items():
                if k in ptr:
                    continue
                ptr[k] = v

        self.assetService.globals.save()
        broker.propagate_state(StateProtocol(
            service=self.assetService.name, status=ServiceStatus.NOT_AVAILABLE.value, to_build=True, to_destroy=True))


SETTINGS_ROUTE = 'settings'

@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler, AsyncIOHandler)
@HTTPRessource(SETTINGS_ROUTE)
class SettingsRessource(BaseHTTPRessource):
    
    
    def __init__(self):
        super().__init__()
        self.configService = Get(ConfigService)
        self.settingService = Get(SettingService)

    #@PingService([SettingService])
    @UseRoles([Role.PUBLIC])
    @UseLimiter(limit_value='1000/minutes')
    @UseServiceLock(SettingService,lockType='reader')
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET],)
    async def get_settings(self,response: Response,request:Request,authPermission=Depends(get_auth_permission)):
        return self.settingService.data
    
    @PingService([JSONServerDBService],infinite_wait=True)
    @UseRoles([Role.ADMIN])
    @UseLimiter(limit_value='1/minutes')
    @UseServiceLock(SettingService,lockType='writer')
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.POST, HTTPMethod.PUT],)
    async def modify_settings(self,response: Response,request:Request, settingsModel:SettingsModel, broker: Annotated[Broker, Depends(Broker)], authPermission=Depends(get_auth_permission),default = Query(False)):
        if default:
            settings = DEFAULT_SETTING
        else:
            settings = settingsModel.model_dump(exclude_none=True)

        current_data = self.settingService.data
        
        if settings == {} or settings == current_data:
            return current_data
        
        current_data.update(settings)

        if settingsModel.AUTH_EXPIRATION is not None and settingsModel.REFRESH_EXPIRATION is not None and current_data[SettingDBConstant.REFRESH_EXPIRATION_SETTING] <= settingsModel.REFRESH_EXPIRATION * 2:
            raise ValueError('REFRESH_EXPIRATION must be at least two times greater than AUTH_EXPIRATION')

        await self.settingService.update_setting(current_data)
        broker.propagate_state(StateProtocol(
            service=self.settingService.name, status=None, to_build=True, to_destroy=False, callback_state_function=self.settingService.aio_get_settings.__name__,
            build_state=SETTING_SERVICE_ASYNC_BUILD_STATE))
        
        return current_data


PROPERTIES_PREFIX = 'properties'
@HTTPRessource(PROPERTIES_PREFIX,routers=[SettingsRessource,GlobalAssetVariableRessource])
class PropertiesRessource(BaseHTTPRessource):
    

    @UseLimiter(limit_value='100/hours')
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.OPTIONS],)
    def properties_options(self,request:Request):
        return {
            "available_routes":[
                {
                    "path":f"/{PROPERTIES_PREFIX}/{VARIABLES_ROUTE}",
                    "description":"Manage global variables",
                    "mount_ressource":SettingsRessource.meta['mount_ressource'],
                    "allowed_methods":[
                        "GET","POST","PUT","DELETE","OPTIONS"
                    ]
                },
                {
                    "path":f"/{PROPERTIES_PREFIX}/{SETTINGS_ROUTE}",
                    "description":"Manage application settings",
                    "mount_ressource":GlobalAssetVariableRessource.meta['mount_ressource'],
                    "allowed_methods":[
                        "GET","POST","PUT","OPTIONS"
                    ]
                }
            ]
        }