from datetime import datetime
from typing import Annotated, Literal, Type
from beanie import Document
from fastapi import Depends, HTTPException, Request, Response,status
from pydantic import BaseModel, ConfigDict
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, MotorErrorHandler, ProfileHandler, ServiceAvailabilityHandler, VaultHandler
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission, ProfilePermission
from app.decorators.pipes import DocumentFriendlyPipe
from app.definition._ressource import R, BaseHTTPRessource, ClassMetaData, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseServiceLock, UseHandler, UsePermission, UsePipe, UseRoles
from app.definition._service import StateProtocol
from app.depends.class_dep import Broker
from app.depends.dependencies import get_auth_permission
from app.models.profile_model import ErrorProfileModel, ProfilModelValues, ProfileModel,PROFILE_TYPE_KEY
from app.services.database_service import MongooseService
from app.services.email_service import EmailSenderService
from app.services.profile_service import ProfileService
from app.classes.profiles import ProfileModelRequestBodyError, ProfileModelTypeDoesNotExistsError
from app.services.secret_service import HCVaultService
from app.utils.helper import subset_model

PROFILE_PREFIX = 'profile'


@PingService([MongooseService])
@UseServiceLock(MongooseService,lockType='reader')
@UseRoles([Role.ADMIN])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,ProfileHandler)
@UseHandler(MotorErrorHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('will be overwritten')
class BaseProfilModelRessource(BaseHTTPRessource):
    model: Type[ProfileModel | Document]
    model_update:Type[ProfileModel | Document]
    model_creds:Type[ProfileModel | Document]
    profileType:str

    @InjectInMethod
    def __init__(self,profileService:ProfileService,vaultService:HCVaultService,mongooseService:MongooseService):
        super().__init__()
        self.profileService = profileService
        self.vaultService = vaultService
        self.mongooseService = mongooseService

    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseHandler(VaultHandler)
    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_profile(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        profileModel = await self.pipe_profil_model(request,'model')
        
        await self.mongooseService.exists_unique(profileModel,True)
        result = await self.profileService.add_profile(profileModel)

        broker.propagate_state(StateProtocol(service=ProfileService,to_build=True,bypass_async_verify=False))
        
        return result

    @PingService([HCVaultService])
    @UseHandler(VaultHandler)
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.DELETE])
    async def delete_profile(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        
        profileModel = await self.mongooseService.get(self.model,profile,True)
        await self.profileService.delete_profile(profileModel)
        
        broker.propagate_state(StateProtocol(service=ProfileService,to_build=True,to_destroy=True,bypass_async_verify=False))

        return profileModel
    
    @UseRoles([Role.PUBLIC])        
    @UsePermission(ProfilePermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.GET])
    async def read_profiles(self,profile:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.mongooseService.get(self.model,profile,True)

    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @HTTPStatusCode(status.HTTP_200_OK)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PUT])
    async def update_profile(self,profile:str,request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        
        profileModel = await self.mongooseService.get(self.model,profile,True)
        modelUpdate = await self.pipe_profil_model(request,'model_update')

        modelUpdate = modelUpdate.model_dump()

        await self.profileService.update_profile(profileModel,modelUpdate)
        return await self.profileService.update_meta_profile(profileModel)

    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseHandler(VaultHandler)
    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PATCH])
    async def set_credentials(self,profile:str,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        
        profileModel:ProfileModel = await self.mongooseService.get(self.model,profile,True)
        modelCreds = await self.pipe_profil_model(request,'model_creds')

        modelCreds = modelCreds.model_dump()

        await self.profileService.update_credentials(profile,modelCreds)
        await self.profileService.update_meta_profile(profileModel)

        return None
       
    @classmethod
    async def pipe_profil_model(cls,request:Request,modelType:Literal['model','model_creds','model_update']): 
        try:
            body = await request.json()  # <- untyped dict
        except:
            raise ProfileModelRequestBodyError
        
        model:Type[ProfileModel | Document] = getattr(cls,modelType,None)
        if model == None:
            raise AttributeError
        
        if not body or body == {}:
            raise ProfileModelRequestBodyError(message = 'Profil Model cannot be empty')

        return model.model_validate(body)

base_meta = BaseProfilModelRessource.meta
base_attr = {'id','revision_id','created_at','last_modified','version'}

def generate_profil_model_ressource(model:Type[ProfileModel],path:str):

    forbid_extra = ConfigDict(extra="forbid")
    
    model_update = subset_model(model,f'Update{model.__name__}',exclude=set(model.unique_indexes).union(model.secrets_keys).union(base_attr),__config__=forbid_extra)
    model_creds = subset_model(model,f'Secrets{model.__name__}',include=set(model.secrets_keys).union(base_attr),__config__=forbid_extra)

    ModelRessource = type(f"{model.__name__}{BaseProfilModelRessource.__name__}",(BaseProfilModelRessource,),{'model':model,PROFILE_TYPE_KEY:path,'model_update':model_update,'model_creds':model_creds})
    setattr(ModelRessource,'meta',base_meta.copy())

    meta:ClassMetaData = getattr(ModelRessource,'meta',{})
    meta['prefix']=path
    meta['classname'] = BaseProfilModelRessource.__name__

    return ModelRessource

@PingService([MongooseService])
@UseServiceLock(MongooseService,lockType='reader')
@UseRoles([Role.ADMIN])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,ProfileHandler)
@UseHandler(MotorErrorHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource(PROFILE_PREFIX,[generate_profil_model_ressource(model,name) for name,model  in ProfilModelValues.items()])
class ProfilRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,mongooseService:MongooseService):
        super().__init__()
        self.mongooseService = mongooseService

    @BaseHTTPRessource.HTTPRoute('/error/',methods=[HTTPMethod.GET])
    async def read_error(self,request:Request,error:ErrorProfileModel, authPermission:AuthPermission=Depends(get_auth_permission)):
        error = error.model_dump()
        return await self.mongooseService.find(ErrorProfileModel,error)
    
    @UsePipe(DocumentFriendlyPipe(include={'ignore'}),before=False)
    @BaseHTTPRessource.HTTPRoute('/error/{error}/',methods=[HTTPMethod.PATCH])
    async def toggle_ignore(self,error:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        
        errorModel = await self.mongooseService.get(ErrorProfileModel,error)
        errorModel.ignore = not errorModel.ignore
        await errorModel.save()

        return errorModel
    
    
    