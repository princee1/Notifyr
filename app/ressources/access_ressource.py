from typing import Annotated

from fastapi import Depends
from starlette import status

from app.classes.auth_permission import AccessTypeAPIModel, AccessTypeModel
from app.decorators.guards import AccessTypeGuard
from app.decorators.handlers import CostHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import AccessPathPipe, SanitizePathParameterPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, LockService, PingService, UseAccess, UseGuard, UseHandler, UseInterceptor, UsePipe
from app.definition._service import StateProtocol
from app.depends.funcs_dep import get_access
from app.depends.variables import SourceMode , source_mode_query
from app.manager.broker_manager import Broker
from app.services.config_service import ConfigService
from app.services.security_service import ACCESS_BUILD_STATE, SecurityService
from app.services.vault_service import VaultService
from app.utils.constant import CostConstant, VaultConstant
from app.utils.helper import generateId
from app.utils.toolbox import RunInThreadPool

@UseHandler(VaultHandler)
@PingService([VaultService])
@UseAccess(accesses={'Admin':True})
@LockService(VaultService,lockType='reader')
@HTTPRessource('access')
class AccessRessource(BaseHTTPRessource):

    def __init__(self,configService:ConfigService,vaultService:VaultService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService

    @UseHandler(CostHandler)
    @UsePipe(AccessPathPipe(False))
    @UseGuard(AccessTypeGuard(False))
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT))
    async def create_access(self,access:str,accessModel:AccessTypeModel,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)]):
        accessModel = AccessTypeAPIModel(token =generateId(75),**accessModel.model_dump(mode='json'))
        accessModel = access.model_dump(mode='json')
        await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,accessModel,access)
        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return accessModel


    @UsePipe(AccessPathPipe(True))
    @UseGuard(AccessTypeGuard(False))
    @BaseHTTPRessource.HTTPRoute('/{access}',methods=[HTTPMethod.PUT],response_class=AccessTypeAPIModel)
    async def set_access(self,access:Annotated[AccessTypeAPIModel,Depends(get_access)],broker:Annotated[Broker,Depends(Broker)]):
        access.token = generateId(75)
        access = access.model_dump(mode='json')
        await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,access,access._path)
        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return access

    @UseHandler(CostHandler)
    @UsePipe(AccessPathPipe(True))
    @UseGuard(AccessTypeGuard(True))
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{access}',methods=[HTTPMethod.DELETE])
    async def delete_access(self,access:Annotated[AccessTypeAPIModel,Depends(get_access)],broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)]):
        await RunInThreadPool(self.vaultService.secrets_engine.delete)(VaultConstant.INTERNAL_API_SECRETS,access._path)
        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return

    @UseGuard(AccessTypeGuard(True))
    @UsePipe(SanitizePathParameterPipe(access=True))
    @BaseHTTPRessource.HTTPRoute('/{access:path}',methods=[HTTPMethod.GET])
    async def read_access(self,access:str='',source:SourceMode=Depends(source_mode_query)):
        match source:
            case 'database':
                if access == '':
                    ...
                else:
                    ...
            case 'memory':
                ...
            case _:
                ...
        
    