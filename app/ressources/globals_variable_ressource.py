from typing import Annotated
from fastapi import Depends, Request, Response, status
from app.container import Get, InjectInMethod
from app.decorators.handlers import GlobalVarHandler, ServiceAvailabilityHandler
from app.decorators.pipes import GlobalPointerIteratorPipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseHandler, UsePipe, ServiceStatusLock
from app.errors.global_var_error import GlobalKeyDoesNotExistsError
from app.models.global_var_model import GlobalVarModel
from app.services.assets_service import AssetService
from app.depends.class_dep import Broker
from app.services.aws_service import AmazonS3Service
from app.depends.variables import global_var_key,force_update
from app.services.config_service import ConfigService
from app.services.file_service import FTPService
from app.utils.helper import PointerIterator

VARIABLES_ROUTE = 'global'
PARAMS_KEY_SEPARATOR = "@"


GLOBAL_KEY_RAISE=1
GLOBAL_KEY = 0

async def save_global_pipe(result):
    assetService:AssetService = Get(AssetService)
    assetService.globals.save()
    return result

@PingService([AssetService])
@UseHandler(ServiceAvailabilityHandler,GlobalVarHandler)
@HTTPRessource(VARIABLES_ROUTE)
class GlobalAssetVariableRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,configService:ConfigService,assetService:AssetService,awsS3Service:AmazonS3Service,ftpService:FTPService):
        super().__init__(None,None)
        self.assetService = assetService
        self.awsS3Service = awsS3Service
        self.ftpService = ftpService
        self.configService = configService
    
    @ServiceStatusLock(AssetService,'reader')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET],)
    async def read_global(self,response:Response,broker:Annotated[Broker,Depends(Broker)],globalIter:PointerIterator=Depends(global_var_key[GLOBAL_KEY])):

        data = self.assetService.globals.data
        if globalIter == None:
            return data
              
        ptr = globalIter.ptr(data)
        if ptr == None:
            raise GlobalKeyDoesNotExistsError(PARAMS_KEY_SEPARATOR,globalIter)
        
        flag,val = globalIter.get_val(ptr)
        if not flag:
            raise GlobalKeyDoesNotExistsError(PARAMS_KEY_SEPARATOR,globalIter)
        return {"value":val}
        
    @ServiceStatusLock(AssetService,'writer')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE],)
    async def delete_global(self,response:Response,broker:Annotated[Broker,Depends(Broker)],globalIter:PointerIterator=Depends(global_var_key[GLOBAL_KEY_RAISE])):
        ptr = globalIter.ptr(self.assetService.globals.data)
        if ptr == None:
            raise GlobalKeyDoesNotExistsError(PARAMS_KEY_SEPARATOR,globalIter)
        
        flag,val = globalIter.get_val(ptr)
        if not flag:
            raise GlobalKeyDoesNotExistsError(PARAMS_KEY_SEPARATOR,globalIter)
        
        globalIter.del_val(ptr)
        self.assetService.globals.save()
        return {"value":val}
        

    @ServiceStatusLock(AssetService,'writer')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UsePipe(GlobalPointerIteratorPipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST,HTTPMethod.PUT],)
    async def upsert_global(self,response:Response,request:Request, broker:Annotated[Broker,Depends(Broker)],globalModel:GlobalVarModel ,globalIter:PointerIterator=Depends(global_var_key[GLOBAL_KEY]),force:bool=Depends(force_update)):
        
        if globalIter == None:
            ptr = self.assetService.globals.data
        else:
            ptr = globalIter.ptr(self.assetService.globals.data)
            if ptr == None:
                raise GlobalKeyDoesNotExistsError(PARAMS_KEY_SEPARATOR,globalIter)

        value = globalModel.model_dump()    
        
        if force:
            ptr.update(globalModel)
            response.status_code = status.HTTP_204_NO_CONTENT
        else:
            response.status_code = status.HTTP_201_CREATED
            for k,v in value.items():
                if k in ptr:
                    continue
                ptr[k] = v

        self.assetService.globals.save()

