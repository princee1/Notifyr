from typing import Annotated, Type
from fastapi import Depends, Request
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, MotorErrorHandler, ProfileHandler, ServiceAvailabilityHandler
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission, ProfilePermission
from app.definition._ressource import R, BaseHTTPRessource, HTTPMethod, HTTPRessource, PingService, UseServiceLock, UseHandler, UsePermission, UsePipe, UseRoles
from app.depends.class_dep import Broker
from app.depends.dependencies import get_auth_permission
from app.models.profile_model import ProfilModelValues, ProfileModel
from app.services.database_service import MongooseService
from app.services.profile_service import ProfileManagerService
from app.classes.profiles import ProfileModelTypeDoesNotExistsError
from app.services.secret_service import HCVaultService

PROFILE_PREFIX = 'profile'

async def pipe_profil_model(profile_type:str,request:Request):
    body = await request.json()  # <- untyped dict
    
    if profile_type not in ProfilModelValues.keys():
        raise ProfileModelTypeDoesNotExistsError(profile_type)
    
    profile_type:Type[ProfileModel] = ProfilModelValues[profile_type]
    return profile_type.model_validate(body)
    
    
def generate_profil_model_ressource(model:Type[ProfileModel],path:str)->Type[R]:

    class Model(model):
        ...

    @PingService([MongooseService])
    @UseServiceLock(MongooseService,lockType='reader')
    @UseRoles([Role.ADMIN])
    @UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,ProfileHandler)
    @UseHandler(MotorErrorHandler)
    @UsePermission(JWTRouteHTTPPermission)
    @HTTPRessource(path)
    class BaseProfilModelRessource(BaseHTTPRessource):
        
        @InjectInMethod
        def __init__(self,profileManagerService:ProfileManagerService,vaultService:HCVaultService):
            super().__init__()
            self.profileManagerService = profileManagerService
            self.vaultService = vaultService

        @PingService([HCVaultService])
        @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
        @UseServiceLock(ProfileManagerService,lockType='reader')
        @UsePermission(AdminPermission)
        @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
        async def create_profile(self,profileModel:Model,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
            ...

        @PingService([HCVaultService])
        @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
        @UseServiceLock(ProfileManagerService,lockType='reader')
        @UsePermission(AdminPermission,ProfilePermission)
        @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PUT])
        async def update_profile(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
            ...
        
        @UseServiceLock(ProfileManagerService,lockType='reader')
        @PingService([HCVaultService])
        @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
        @UsePermission(AdminPermission,ProfilePermission)
        @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.DELETE])
        async def delete_profile(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
            ...

        @UseRoles([Role.PUBLIC])        
        @UsePermission(ProfilePermission)
        @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.GET])
        async def read_profiles(self,profile:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
            ...

        
        @PingService([HCVaultService])
        @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
        @UseServiceLock(ProfileManagerService,lockType='reader')
        @UsePermission(AdminPermission,ProfilePermission)
        @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PUT,HTTPMethod.POST])
        async def set_credentials(self,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
            ...
    
    return BaseProfilModelRessource

@HTTPRessource(PROFILE_PREFIX,)
class ProfilRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,mongooseService:MongooseService):
        super().__init__()
        self.mongooseService = mongooseService

    @PingService([MongooseService])
    @UseServiceLock(MongooseService,lockType='reader')
    @UseRoles([Role.ADMIN])
    @UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,ProfileHandler)
    @UseHandler(MotorErrorHandler)
    @UsePermission(JWTRouteHTTPPermission)
    @BaseHTTPRessource.HTTPRoute('/error/',methods=[HTTPMethod.GET])
    async def read_error(self,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...