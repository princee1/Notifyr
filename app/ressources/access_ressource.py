from typing import Annotated, Literal, Optional

from fastapi import Depends, HTTPException, Response, Request
from pydantic import Field, field_validator
from starlette import status

from app.classes.auth_permission import AccessAPIInfo, AccessAlreadyExistsError, AccessDoesNotExistsError, AccessHardLimitReachedError, AccessTypeAPIModel, AccessTypeModel, ClientTypeLiteral
from app.container import InjectInMethod
from app.cost.access_cost import AccessCost
from app.decorators.access import AdminModificationAccess
from app.decorators.guards import AccessAdminGuard, access_confirm_guard
from app.decorators.handlers import AccessHandler, CostHandler, DataSourceHandler, RedisHandler, VaultHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.pipes import AccessPathPipe, SanitizePathParameterPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, LockService, PingService, Throttle, UseAccess, UseGuard, UseHandler, UseInterceptor, UseLimiter, UsePipe, UseProtection
from app.definition._service import StateProtocol
from app.depends.dependencies import get_access_info
from app.depends.funcs_dep import get_access
from app.depends.variables import SourceMode , source_mode_query,confirm_query
from app.errors.depends_error import DataSourceNotSupportedError
from app.manager.broker_manager import Broker
from app.services.config_service import ConfigService
from app.services.security_service import ACCESS_BUILD_STATE, SecurityService, AccessVaultConstant
from app.services.vault_service import VaultService
from app.utils.constant import CostConstant, VaultConstant
from app.utils.helper import generateId, uuid_v1_mc
from app.utils.toolbox import RunInThreadPool

@PingService([VaultService])
@UseHandler(AccessHandler,VaultHandler)
@LockService(VaultService,lockType='reader')
@HTTPRessource('access')
class AccessRessource(BaseHTTPRessource):

    class CreateAccessTypeModel(AccessTypeModel):
        @field_validator('type',mode='after')
        def validate_type(cls,t:ClientTypeLiteral):
            if t == 'Admin' or t == 'System': 
                raise ValueError('We cannot create this new access type')
            return t

        @field_validator('alias',mode='after')
        def validate_alias(cls,alias:str):
            if alias == 'Notifyr Admin' or alias == 'Notifyr System':
                raise ValueError('We cannot set the same alias as the admin')

            if 'admin' in alias.lower() or 'system' in alias.lower():
                raise ValueError('Alias contains invalid sequence characters (admin, system)')

            return alias

    @staticmethod
    def compute_access_id():
        return str(uuid_v1_mc(1))

    @InjectInMethod()
    def __init__(self,configService:ConfigService,vaultService:VaultService,securityService:SecurityService):
        super().__init__(None,None)
        self.configService = configService
        self.vaultService = vaultService
        self.securityService = securityService

    @Throttle(uniform=(150,250))
    @UsePipe(AccessPathPipe(False))
    @UseGuard(AccessAdminGuard(False))
    @UseHandler(CostHandler,RedisHandler)
    @UseLimiter('10/day',key_func='access')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UseAccess(accesses={'Admin':True,'System':True})
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST],response_class=AccessTypeAPIModel)
    async def create_access(self,request:Request,response:Response,accessModel:CreateAccessTypeModel,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[AccessCost,Depends(AccessCost)],access:str=Depends(compute_access_id),accessInfo:AccessAPIInfo=Depends(get_access_info)):
        path = AccessVaultConstant.ACCESS_PATH()
        accesses = await RunInThreadPool(self.vaultService.secrets_engine.list)(VaultConstant.INTERNAL_API_SECRETS,path)
        if len(accesses) >= 15:
            raise AccessHardLimitReachedError(15)

        for aid in accesses:
            if aid == 'admin' or aid == 'system':
                continue
            if access.endswith(aid):
                raise AccessAlreadyExistsError(access,'uuid')

        for aid,a in self.vaultService.secrets_engine.view(VaultConstant.INTERNAL_API_SECRETS,path,source=accesses):
            if a['type'] == 'Admin' or a['type'] == 'System':
                continue
            if a['alias'] == accessModel.alias:
                raise AccessAlreadyExistsError(aid,'uuid')

        accessModel = AccessTypeAPIModel(token =f'app:{generateId(75)}',**accessModel.model_dump(mode='json'))
        accessModel = accessModel.model_dump(mode='json')
        await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,accessModel,access)

        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return accessModel

    @Throttle(uniform=(150,250))
    @UsePipe(AccessPathPipe(True))
    @UseLimiter('10/day',key_func='access')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UsePipe(SanitizePathParameterPipe({},access=True))
    @UseGuard(access_confirm_guard,AccessAdminGuard(True))
    @UseAccess(AdminModificationAccess,accesses={'Admin':True,'System':True})
    @BaseHTTPRessource.HTTPRoute('/{access:path}',methods=[HTTPMethod.PATCH],response_class=AccessTypeAPIModel)
    async def rotate_access(self,request:Request,response:Response,access:Annotated[AccessTypeAPIModel|Literal[''],Depends(get_access)],broker:Annotated[Broker,Depends(Broker)],confirm:bool=Depends(confirm_query),accessInfo:AccessAPIInfo=Depends(get_access_info)):
        if access == '':
            path = AccessVaultConstant.ACCESS_PATH()
            accesses:list[tuple[str,dict]] = list(await RunInThreadPool(self.vaultService.secrets_engine.view)(VaultConstant.INTERNAL_API_SECRETS,path))
            for aid,a in accesses:
                if aid == 'system' or  a['type'] == 'System':
                    continue
                if aid == 'admin' and accessInfo['type'] != 'System':
                    continue
                if a['type'] == 'Admin' and accessInfo['type'] != 'System':
                    continue
                a['token'] = f"app:{generateId(75)}"
                path = AccessVaultConstant.ACCESS_PATH(aid)
                await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,a,path)

            broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
            return
        else:
            access.token = f"app:{generateId(75)}"
            access = access.model_dump(mode='json')
            await RunInThreadPool(self.vaultService.secrets_engine.put)(VaultConstant.INTERNAL_API_SECRETS,access,access._path)
            response.status_code = status.HTTP_200_OK

            broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
            return access


    @Throttle(uniform=(150,250))
    @UsePipe(AccessPathPipe(True))
    @UseHandler(CostHandler,RedisHandler)
    @UseLimiter('10/day',key_func='access')
    @UseAccess(accesses={'Admin':True,'System':True})
    @UsePipe(SanitizePathParameterPipe({},access=True))
    @UseGuard(access_confirm_guard,AccessAdminGuard(False))
    @UseInterceptor(DataCostInterceptor(CostConstant.CLIENT_CREDIT,'refund'))
    @BaseHTTPRessource.HTTPRoute('/{access:path}',methods=[HTTPMethod.DELETE])
    async def delete_access(self,request:Request,response:Response,access:Annotated[AccessTypeAPIModel|Literal[''],Depends(get_access)],broker:Annotated[Broker,Depends(Broker)],cost:Annotated[AccessCost,Depends(AccessCost)],confirm:bool=Depends(confirm_query),accessInfo:AccessAPIInfo=Depends(get_access_info)):
        res = []
        if access == '':
            path = AccessVaultConstant.ACCESS_PATH()
            accesses = await RunInThreadPool(self.vaultService.secrets_engine.list)(VaultConstant.INTERNAL_API_SECRETS,path)
            for aid in accesses:
                if aid == 'system' or aid == 'admin':
                    continue
                res.append(aid)
                path = AccessVaultConstant.ACCESS_PATH(aid)
                await RunInThreadPool(self.vaultService.secrets_engine.delete)(VaultConstant.INTERNAL_API_SECRETS,path)
        else:
            await RunInThreadPool(self.vaultService.secrets_engine.delete)(VaultConstant.INTERNAL_API_SECRETS,access._path)
            res.append(access._input)

        broker.propagate(StateProtocol(service=SecurityService,to_build=True,build_state=ACCESS_BUILD_STATE))
        return res


    @Throttle(uniform=(150,250))
    @UseHandler(DataSourceHandler)
    @UseGuard(AccessAdminGuard(True))
    @UseLimiter('5/hour',key_func='access')
    @LockService(SecurityService,lockType='reader')
    @UsePipe(SanitizePathParameterPipe({},access=True))
    @UseAccess(AdminModificationAccess,accesses={'Admin':True,'System':True})
    @BaseHTTPRessource.HTTPRoute('/{access:path}',methods=[HTTPMethod.GET])
    async def read_access(self,request:Request,response:Response,access:str='',source:SourceMode=Depends(source_mode_query),accessInfo:AccessAPIInfo=Depends(get_access_info)):
        match source:
            case 'database':
                if access == '':
                    res= {}
                    path = AccessVaultConstant.ACCESS_PATH()
                    accesses:list[tuple[str,dict]] = list(await RunInThreadPool(self.vaultService.secrets_engine.view)(VaultConstant.INTERNAL_API_SECRETS,path))
                    for (acs_id,a) in accesses:
                        if a['id'] == 'system' or a['type'] == 'System':
                            continue
                        res[acs_id] = a
                    return res
                else:
                    path = AccessVaultConstant.ACCESS_PATH(access)
                    return await RunInThreadPool(self.vaultService.secrets_engine.read)(VaultConstant.INTERNAL_API_SECRETS,path)
            case 'memory':
                res = {}
                for _access in self.securityService.API_KEY.values():
                    if a['id'] == 'system' or a['type'] == 'System':
                        continue
                    if access == '':
                        res[_access['id']]=_access
                    elif access == _access['id']:
                        return _access
                if access == '':                
                    return res
                raise AccessDoesNotExistsError(access)
            case _:
                raise DataSourceNotSupportedError(source,['database','memory'])
                
        
    