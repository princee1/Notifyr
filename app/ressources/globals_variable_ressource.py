from typing import Annotated
from fastapi import Depends, Request, Response, status
from app.classes.auth_permission import Role
from app.container import Get, InjectInMethod
from app.decorators.handlers import GlobalVarHandler, ServiceAvailabilityHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.decorators.pipes import GlobalPointerIteratorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseHandler, UseLimiter, UsePermission, UsePipe, ServiceStatusLock, UseRoles
from app.definition._service import StateProtocol, ServiceStatus
from app.depends.dependencies import get_auth_permission
from app.errors.global_var_error import GlobalKeyDoesNotExistsError
from app.models.global_var_model import GlobalVarModel
from app.services.assets_service import AssetService
from app.depends.class_dep import Broker
from app.services.aws_service import AmazonS3Service
from app.depends.variables import global_var_key, force_update
from app.services.config_service import ConfigService
from app.services.file_service import FTPService
from app.utils.helper import APIFilterInject, PointerIterator

VARIABLES_ROUTE = 'global'
PARAMS_KEY_SEPARATOR = "@"

GLOBAL_KEY_RAISE = 1
GLOBAL_KEY = 0


@PingService([AssetService])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler, GlobalVarHandler)
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
    @ServiceStatusLock(AssetService, 'reader')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UseRoles([Role.PUBLIC])
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET],)
    async def read_global(self, response: Response,request:Request, globalIter: PointerIterator = Depends(global_var_key[GLOBAL_KEY]), authPermission=Depends(get_auth_permission)):

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

    @UseLimiter(limit_value='100/minutes')
    @ServiceStatusLock(AssetService, 'writer')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UseRoles([Role.ADMIN])
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.DELETE],)
    async def delete_global(self, response: Response,request:Request, broker: Annotated[Broker, Depends(Broker)], globalIter: PointerIterator = Depends(global_var_key[GLOBAL_KEY_RAISE]), authPermission=Depends(get_auth_permission)):
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

    @UseLimiter(limit_value='50/minutes')
    @ServiceStatusLock(AssetService, 'writer')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UseRoles([Role.ADMIN])
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.POST, HTTPMethod.PUT],)
    async def upsert_global(self, response: Response, request: Request, broker: Annotated[Broker, Depends(Broker)], globalModel: GlobalVarModel, globalIter: PointerIterator = Depends(global_var_key[GLOBAL_KEY]), force: bool = Depends(force_update), authPermission=Depends(get_auth_permission)):

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
