from typing import Annotated, Type
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, MotorErrorHandler, ProfileHandler, ServiceAvailabilityHandler, VaultHandler
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission, ProfilePermission
from app.decorators.pipes import DocumentFriendlyPipe
from app.definition._ressource import R, BaseHTTPRessource, ClassMetaData, HTTPMethod, HTTPRessource, PingService, UseServiceLock, UseHandler, UsePermission, UsePipe, UseRoles
from app.definition._service import StateProtocol
from app.depends.class_dep import Broker
from app.depends.dependencies import get_auth_permission
from app.models.profile_model import ProfilModelValues, ProfileModel,PROFILE_TYPE_KEY
from app.services.database_service import MongooseService
from app.services.email_service import EmailSenderService
from app.services.profile_service import ProfileService
from app.classes.profiles import ProfileCreationModelError, ProfileModelTypeDoesNotExistsError
from app.services.secret_service import HCVaultService

PROFILE_PREFIX = 'profile'


@PingService([MongooseService])
@UseServiceLock(MongooseService,lockType='reader')
@UseRoles([Role.ADMIN])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,ProfileHandler)
@UseHandler(MotorErrorHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('')
class BaseProfilModelRessource(BaseHTTPRessource):
    model: Type[ProfileModel | BaseModel]
    profileType:str

    @InjectInMethod
    def __init__(self,profileService:ProfileService,vaultService:HCVaultService):
        super().__init__()
        self.profileService = profileService
        self.vaultService = vaultService

    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseHandler(VaultHandler)
    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_profile(self,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        profileModel = await self.pipe_profil_model(request)
        result = await self.profileService.add_profile(profileModel)

        broker.propagate_state(StateProtocol(service=ProfileService,to_build=True,to_destroy=True,bypass_async_verify=False))
        broker.wait(seconds=1.2)
        broker.propagate_state(StateProtocol(service=EmailSenderService,to_build=True,to_destroy=True,bypass_async_verify=False))

        return result

    @PingService([HCVaultService])
    @UseHandler(VaultHandler)
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.DELETE])
    async def delete_profile(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        ...
        await self.profileService.get_profile(self.model,profile_id=profile)
        result = await self.profileService.delete_profile()

        broker.propagate_state(StateProtocol(service=ProfileService,to_build=True,to_destroy=True,bypass_async_verify=False))
        broker.wait(seconds=1.2)
        broker.propagate_state(StateProtocol(service=EmailSenderService,to_build=True,to_destroy=True,bypass_async_verify=False))

    
    @UseRoles([Role.PUBLIC])        
    @UsePermission(ProfilePermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.GET])
    async def read_profiles(self,profile:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        
        await self.profileService.get_profile(self.model)


    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PUT])
    async def update_profile(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseHandler(VaultHandler)
    @UsePermission(AdminPermission)
    @BaseHTTPRessource.HTTPRoute('/creds/{profile}/',methods=[HTTPMethod.PUT,HTTPMethod.POST])
    async def set_credentials(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        
        await self.profileService.get_profile(self.model,profile)
        
    
    @classmethod
    async def pipe_profil_model(cls,request:Request):
        try:
            body = await request.json()  # <- untyped dict
        except:
            raise ProfileCreationModelError
        body[PROFILE_TYPE_KEY] = cls.profileType
        return cls.model.model_validate(body)

base_meta = BaseProfilModelRessource.meta

def generate_profil_model_ressource(model:Type[ProfileModel],path):

    ModelRessource = type(f"{model.__name__}{BaseProfilModelRessource.__name__}",(BaseProfilModelRessource,),{'model':model,PROFILE_TYPE_KEY:path})
    setattr(ModelRessource,'meta',base_meta.copy())
    meta:ClassMetaData = getattr(ModelRessource,'meta',{})
    meta['prefix']=path
    meta['classname'] = BaseProfilModelRessource.__name__
    return ModelRessource

@HTTPRessource(PROFILE_PREFIX,[generate_profil_model_ressource(model,name) for name,model  in ProfilModelValues.items()])
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