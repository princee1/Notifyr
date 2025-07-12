from typing import Annotated
from fastapi import Depends, Response, status
from app.container import InjectInMethod
from app.decorators.handlers import GlobalVarHandler, ServiceAvailabilityHandler
from app.decorators.pipes import GlobalPointerIteratorRipe
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, PingService, UseHandler, UsePipe, UseStatusLock
from app.errors.global_var_error import GlobalKeyDoesNotExistsError
from app.services.assets_service import AssetService
from app.depends.class_dep import Broker
from app.services.aws_service import AmazonS3Service
from app.depends.variables import global_var_key
from app.services.file_service import FTPService
from app.utils.helper import DICT_SEP, flatten_dict
from app.utils.helper import PointerIterator

VARIABLES_ROUTE = 'variable'
PARAMS_KEY_SEPARATOR = "@"


@PingService(AssetService)
@UseHandler(ServiceAvailabilityHandler,GlobalVarHandler)
@HTTPRessource(VARIABLES_ROUTE)
class GlobalAssetVariableRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,assetService:AssetService,awsS3Service:AmazonS3Service,ftpService:FTPService):
        super().__init__(None,None)
        self.assetService = assetService
        self.awsS3Service = awsS3Service
        self.ftpService = ftpService
    
    @UseStatusLock(AssetService,'reader')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UsePipe(GlobalPointerIteratorRipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET],)
    async def read_global(self,response:Response,broker:Annotated[Broker,Depends(Broker)],globalIter:PointerIterator=Depends(global_var_key)):

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
        
    
    @UseStatusLock(AssetService,'writer')
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @UsePipe(GlobalPointerIteratorRipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT],)
    async def update_global(self,response:Response,broker:Annotated[Broker,Depends(Broker)],globalIter:PointerIterator=Depends(global_var_key)):
        ...

    @UseStatusLock(AssetService,'writer')
    @HTTPStatusCode(status.HTTP_200_OK)
    @UsePipe(GlobalPointerIteratorRipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE],)
    async def delete_global(self,response:Response,broker:Annotated[Broker,Depends(Broker)],globalIter:PointerIterator=Depends(global_var_key)):
        ...

    @UseStatusLock(AssetService,'writer')
    @HTTPStatusCode(status.HTTP_201_CREATED)
    @UsePipe(GlobalPointerIteratorRipe(PARAMS_KEY_SEPARATOR))
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST],)
    async def add_global(self,response:Response,broker:Annotated[Broker,Depends(Broker)],globalIter:PointerIterator=Depends(global_var_key)):
        ...
