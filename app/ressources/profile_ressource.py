from typing import Annotated, Literal, Type
from beanie import Document
from fastapi import Depends,Request, Response,status
from pydantic import ConfigDict
from app.classes.auth_permission import AuthPermission, Role
from app.classes.mongo import MongoCondition, simple_number_validation
from app.container import InjectInMethod,Get
from app.decorators.handlers import AsyncIOHandler, CostHandler, MiniServiceHandler, MotorErrorHandler, ProfileHandler, PydanticHandler, ServiceAvailabilityHandler, VaultHandler,CeleryControlHandler
from app.decorators.interceptors import DataCostInterceptor
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission, ProfilePermission
from app.decorators.pipes import DocumentFriendlyPipe, MiniServiceInjectorPipe
from app.definition._cost import DataCost
from app.definition._ressource import BaseHTTPRessource, ClassMetaData, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseInterceptor, UseServiceLock, UseHandler, UsePermission, UsePipe, UseRoles
from app.definition._service import MiniStateProtocol, StateProtocol
from app.depends.dependencies import get_auth_permission
from app.depends.funcs_dep import get_profile
from app.classes.profiles import ProfilModelValues, BaseProfileModel, ErrorProfileModel
from app.manager.broker_manager import Broker
from app.services.celery_service import CeleryService, ChannelMiniService
from app.services.config_service import ConfigService
from app.services.database_service import MongooseService, RabbitMQService, RedisService
from app.services.profile_service import ProfileMiniService, ProfileService
from app.classes.profiles import ProfileModelAddConditionError, ProfileModelConditionWrongMethodError, ProfileModelRequestBodyError, ProfileModelTypeDoesNotExistsError
from app.services.secret_service import HCVaultService
from app.services.task_service import TaskService
from app.utils.constant import CostConstant
from app.utils.helper import subset_model

PROFILE_PREFIX = 'profile'


@PingService([MongooseService])
@UseServiceLock(MongooseService,lockType='reader',check_status=False)
@UseRoles([Role.ADMIN])
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,MotorErrorHandler,ProfileHandler)
@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('will be overwritten')
class BaseProfilModelRessource(BaseHTTPRessource):
    model: Type[BaseProfileModel | Document]
    model_update:Type[BaseProfileModel | Document]
    model_creds:Type[BaseProfileModel | Document]
    profileType:str

    @InjectInMethod()
    def __init__(self,profileService:ProfileService,vaultService:HCVaultService,mongooseService:MongooseService,celeryService:CeleryService,redisService:RedisService,taskService:TaskService):
        super().__init__()
        self.profileService = profileService
        self.vaultService = vaultService
        self.mongooseService = mongooseService
        self.celeryService= celeryService
        self.redisService = redisService
        self.taskService = taskService
    
        self.pms_callback = ProfileMiniService.async_create_profile.__name__
        self.configService = Get(ConfigService)
        self.rabbitmqService = Get(RabbitMQService)

    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,MongooseService,lockType='reader')
    @UseHandler(VaultHandler,MiniServiceHandler,PydanticHandler,CostHandler,CeleryControlHandler)
    @UsePermission(AdminPermission)
    @UseInterceptor(DataCostInterceptor(CostConstant.PROFILE_CREDIT))
    @UsePipe(DocumentFriendlyPipe,before=False)
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_profile(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],authPermission:AuthPermission=Depends(get_auth_permission)):
        profileModel = await self.pipe_profil_model(request,'model')
        
        await self.mongooseService.primary_key_constraint(profileModel,True)
        await self.mongooseService.exists_unique(profileModel,True)
        await self.profile_model_satisfaction(profileModel)

        result = await self.profileService.add_profile(profileModel)
        broker.propagate_state(StateProtocol(service=ProfileService,to_destroy=True,to_build=True,bypass_async_verify=False))

        profileMiniService = ProfileMiniService(None,None,self.redisService,self.taskService,result)
        await ChannelMiniService(profileMiniService,self.configService,self.rabbitmqService,self.redisService,self.celeryService).create_queue()

        return result

    @UsePermission(AdminPermission)
    @PingService([HCVaultService])
    @UseHandler(VaultHandler,MiniServiceHandler,CostHandler,CeleryControlHandler)
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False,infinite_wait=True)
    @UseServiceLock(ProfileService,CeleryService,lockType='reader',as_manager=True,motor_fallback=True)
    @UseInterceptor(DataCostInterceptor(CostConstant.PROFILE_CREDIT,'refund'))
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'),)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.DELETE])
    async def delete_profile(self,profile:str,channel:Annotated[ChannelMiniService,Depends(get_profile)],request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],cost:Annotated[DataCost,Depends(DataCost)],authPermission:AuthPermission=Depends(get_auth_permission)):
        
        profileModel = await self.mongooseService.get(self.model,profile,True)
        await self.profileService.delete_profile(profileModel)
        await channel.delete_queue()
        
        broker.propagate_state(StateProtocol(service=ProfileService,to_build=True,to_destroy=True,bypass_async_verify=False))
        return profileModel
    
    @UseHandler(PydanticHandler,CeleryControlHandler)
    @UsePermission(AdminPermission)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'),)
    @UseServiceLock(ProfileService,CeleryService,lockType='reader',as_manager=True,motor_fallback=True)
    @HTTPStatusCode(status.HTTP_200_OK)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PUT])
    async def update_profile(self,profile:str,channel:Annotated[ChannelMiniService,Depends(get_profile)],request:Request,broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        
        profileModel = await self.mongooseService.get(self.model,profile,True)
        modelUpdate = await self.pipe_profil_model(request,'model_update')

        await profileModel.update_profile(modelUpdate)

        await self.mongooseService.primary_key_constraint(profileModel,True)
        await self.mongooseService.exists_unique(profileModel,True)
        await profileModel.update_meta_profile()

        await channel.refresh_worker_state()
        broker.propagate_state(MiniStateProtocol(service=ProfileService,id=profile,to_destroy=True,callback_state_function=self.pms_callback))
        return profileModel
    
    @PingService([HCVaultService])
    @UseServiceLock(HCVaultService,lockType='reader',check_status=False)
    @UseServiceLock(ProfileService,CeleryService,lockType='reader',as_manager=True,motor_fallback=True)
    @UseHandler(VaultHandler,PydanticHandler,CeleryControlHandler)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'))
    @UsePermission(AdminPermission)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.PATCH])
    async def set_credentials(self,profile:str,channel:Annotated[ChannelMiniService,Depends(get_profile)],request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)], authPermission:AuthPermission=Depends(get_auth_permission)):
        
        profileModel:BaseProfileModel = await self.mongooseService.get(self.model,profile,True)
        modelCreds = await self.pipe_profil_model(request,'model_creds')

        modelCreds = modelCreds.model_dump()
        await self.profile_model_satisfaction(modelCreds)

        await self.profileService.update_credentials(profile,modelCreds,self.model._vault)
        await profileModel.update_meta_profile()

        await channel.refresh_worker_state()

        broker.propagate_state(MiniStateProtocol(service=ProfileService,id=profile,to_destroy=True,callback_state_function=self.pms_callback))
        return None
       
    @UseRoles([Role.PUBLIC])
    @UseHandler(MiniServiceHandler)
    @UsePermission(ProfilePermission)
    @UseServiceLock(ProfileService,lockType='reader',as_manager=True,motor_fallback=True)
    @UsePipe(DocumentFriendlyPipe,before=False)
    @BaseHTTPRessource.HTTPRoute('/{profile}/',methods=[HTTPMethod.GET])
    async def read_profiles(self,profile:str,request:Request,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.mongooseService.get(self.model,profile,True)

    @UseRoles([Role.PUBLIC])
    @UseHandler(MiniServiceHandler,CeleryControlHandler)
    @UsePipe(MiniServiceInjectorPipe(CeleryService,'channel'),)
    @UsePermission(ProfilePermission)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UseServiceLock(ProfileService,CeleryService,lockType='reader',as_manager=True,motor_fallback=True)
    @BaseHTTPRessource.HTTPRoute('/refresh/{profile}/',methods=[HTTPMethod.PATCH])
    async def refresh_memory_state(self,profile:str,request:Request,channel:Annotated[ChannelMiniService,Depends(get_profile)],broker:Annotated[Broker,Depends(Broker)],authPermission:AuthPermission=Depends(get_auth_permission)):
        await channel.refresh_worker_state()
        broker.propagate_state(MiniStateProtocol(service=ProfileService,id=profile,to_destroy=True,callback_state_function=self.pms_callback))
        

    
    @classmethod
    async def pipe_profil_model(cls,request:Request,modelType:Literal['model','model_creds','model_update']): 
        try:
            body = await request.json()  # <- untyped dict
        except:
            raise ProfileModelRequestBodyError
        
        model:Type[BaseProfileModel | Document] = getattr(cls,modelType,None)
        if model == None:
            raise AttributeError
        
        if not body or body == {}:
            raise ProfileModelRequestBodyError(message = 'Profil Model cannot be empty')

        return model.model_validate(body)

    async def profile_model_satisfaction(self,profileModel:BaseProfileModel | dict):
        
        def validate_filter(m:MongoCondition,p_dump):
            try:
                for k,v in m['filter'].items():
                    if v == p_dump[k]:
                        continue
                    else:
                        return False
            except KeyError:
                return False
            return True

        mc:MongoCondition = self.model._condition
        if mc == None:
            return
        
        if isinstance(profileModel,BaseProfileModel):
            profile_dump = profileModel.model_dump(mode='json')    
        else:
            profile_dump = profileModel

        if not validate_filter(mc,profile_dump):
            return

        count = await self.mongooseService.count(self.model,mc['filter'])
        if mc['method'] != 'simple-number-validation':
            raise ProfileModelConditionWrongMethodError

        if simple_number_validation(count,mc['rule']):
            raise ProfileModelAddConditionError()
        
        if not mc.get('force',False):
            return

        for k,v in mc['filter'].items():
            if not isinstance(v,(str,int,float,bool,list,dict)):
                continue

            if isinstance(profileModel,BaseProfileModel):
                print(k,v)
                setattr(profileModel,k,v)
            else:
                profile_dump[k] = v
            

base_meta = BaseProfilModelRessource.meta
base_attr = {'id','revision_id','created_at','last_modified','version'}

def generate_profil_model_ressource(model:Type[BaseProfileModel],path:str):

    forbid_extra = ConfigDict(extra="forbid")
    
    model_update = subset_model(model,f'Update{model.__name__}',exclude=set(model._unique_indexes).union(model._secrets_keys).union(base_attr),__config__=forbid_extra)
    model_creds = subset_model(model,f'Secrets{model.__name__}',include=set(model._secrets_keys).union(base_attr),__config__=forbid_extra)

    ModelRessource = type(f"{model.__name__}{BaseProfilModelRessource.__name__}",(BaseProfilModelRessource,),{'model':model,'profileType':path,'model_update':model_update,'model_creds':model_creds})
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
    
    @InjectInMethod()
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
    
    @UsePipe(DocumentFriendlyPipe(include={'ignore'}),before=False)
    @BaseHTTPRessource.HTTPRoute('/all/',methods=[HTTPMethod.GET])
    async def get_all(self,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        return await self.mongooseService.find_all(BaseProfileModel)
    
    
    