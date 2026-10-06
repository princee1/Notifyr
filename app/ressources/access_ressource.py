from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Response, Request
from pydantic import Field, field_validator
from starlette import status

from app.classes.auth_permission import AccessAlreadyExistsError, AccessDoesNotExistsError, AccessHardLimitReachedError, AccessTypeAPIModel, AccessTypeModel, ClientTypeLiteral
from app.container import InjectInMethod
from app.decorators.guards import AccessTypeGuard
from app.decorators.handlers import AccessHandler, CostHandler, DataSourceHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import AccessPathPipe, SanitizePathParameterPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, LockService, PingService, Throttle, UseAccess, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePipe
from app.definition._service import StateProtocol
from app.depends.funcs_dep import get_access
from app.depends.variables import SourceMode , source_mode_query
from app.errors.depends_error import DataSourceNotSupportedError
from app.manager.broker_manager import Broker
from app.services.config_service import ConfigService
from app.services.security_service import ACCESS_BUILD_STATE, SecurityService
from app.services.vault_service import VaultService
from app.utils.constant import CostConstant, VaultConstant
from app.utils.helper import generateId, uuid_v1_mc
from app.utils.toolbox import RunInThreadPool

@PingService([VaultService])
@UseAccess(accesses={'Admin':True})
@UseHandler(AccessHandler,VaultHandler)
@LockService(VaultService,lockType='reader')
@HTTPRessource('access')
class AccessRessource(BaseHTTPRessource):

    class CreateAccessTypeModel(AccessTypeModel):
        @field_validator('type',mode='after')
        def validate_type(cls,t:ClientTypeLiteral):
            if t == 'Admin':
                raise ValueError('We cannot create a new admin access')
            return t

    @staticmethod
    def compute_access_id():
        return str(uuid_v1_mc(1))

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,securityService:SecurityService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.securityService = securityService

    @UseHandler(CostHandler)
    @Throttle(uniform=(150,250))
    @UsePipe(AccessPathPipe(False))
    @UseGuard(AccessTypeGuard(False))
    @UseLimiter('10/day',key_func='access')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST],response_class=AccessTypeAPIModel)
    async def create_access(self,request:Request,response:Response,accessModel:CreateAccessTypeModel,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],access:str=Depends(compute_access_id)):
        accesses = await RunInThreadPool(self.vaultService.secrets_engine.list)(VaultConstant.INTERNAL_API_SECRETS,'ACCESS')
        if len(accesses) >= 15:
            raise AccessHardLimitReachedError(15)

        if access in accesses:
            raise AccessAlreadyExistsError(access,'uuid')

        for access_id,a in self.vaultService.secrets_engine.view(VaultConstant.INTERNAL_API_SECRETS,'ACCESS',sources =accesses):
            if a['alias'] == accessModel.alias:
                raise AccessAlreadyExistsError(access_id,'uuid')

        accessModel = AccessTypeAPIModel(token =generateId(75),**accessModel.model_dump(mode='json'))
        accessModel = accessModel.model_dump(mode='json')
        await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,accessModel,access)

        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return accessModel

    @Throttle(uniform=(150,250))
    @UsePipe(AccessPathPipe(True))
    @UseGuard(AccessTypeGuard(False))
    @UseLimiter('10/day',key_func='access')
    @BaseHTTPRessource.HTTPRoute('/{access}/',methods=[HTTPMethod.PUT],response_class=AccessTypeAPIModel)
    async def set_access(self,request:Request,response:Response,access:Annotated[AccessTypeAPIModel,Depends(get_access)],broker:Annotated[Broker,Depends(Broker)]):
        access.token = generateId(75)
        access = access.model_dump(mode='json')
        await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,access,access._path)

        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return access

    @UseHandler(CostHandler)
    @Throttle(uniform=(150,250))
    @UsePipe(AccessPathPipe(True))
    @UseGuard(AccessTypeGuard(True))
    @UseLimiter('10/day',key_func='access')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{access}/',methods=[HTTPMethod.DELETE])
    async def delete_access(self,request:Request,response:Response,access:Annotated[AccessTypeAPIModel,Depends(get_access)],broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)]):
        await RunInThreadPool(self.vaultService.secrets_engine.delete)(VaultConstant.INTERNAL_API_SECRETS,access._path)

        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return

    @Throttle(uniform=(150,250))
    @UseHandler(DataSourceHandler)
    @UseGuard(AccessTypeGuard(True))
    @UseLimiter('3/minutes',key_func='access')
    @LockService(SecurityService,lockType='reader')
    @UsePipe(SanitizePathParameterPipe({},access=True))
    @BaseHTTPRessource.HTTPRoute('/{access:path}',methods=[HTTPMethod.GET])
    async def read_access(self,request:Request,response:Response,access:str='',source:SourceMode=Depends(source_mode_query)):
        match source:
            case 'database':
                if access == '':
                    res= {}
                    accesses:list[tuple[str,dict]] = list(await RunInThreadPool(self.vaultService.secrets_engine.view)(VaultConstant.INTERNAL_API_SECRETS,'ACCESS'))
                    for access_id,access in accesses:
                        res[access_id] = access
                    return accesses
                else:
                    return await RunInThreadPool(self.vaultService.secrets_engine.read)(VaultConstant.INTERNAL_API_SECRETS,f'ACCESS/{access}')
            case 'memory':
                res = {}
                for _access in self.securityService.API_KEY.values():
                    if access == '':
                        res[_access['access']]=_access
                    elif access == _access['access']:
                        return _access
                if access == '':                
                    return res
                raise AccessDoesNotExistsError(access)
            case _:
                raise DataSourceNotSupportedError(source,['database','memory'])
                
        
    