from typing import Any, Type
from fastapi.responses import JSONResponse
from typing_extensions import Literal
from fastapi import BackgroundTasks, Request, Response,status
from app.container import Get
from app.definition._utils_decorator import Interceptor, InterceptorDefaultException
from app.depends.class_dep import KeepAliveQuery
from app.depends.res_cache import ResponseCacheInterface
from app.services.database_service import MemCachedService
from app.utils.helper import copy_response


class KeepAliveResponseInterceptor(Interceptor):
    
    def intercept_before(self):
        ...

    def intercept_after(self,result:Any|Response, keepAliveConn:KeepAliveQuery,request:Request):
        keepAliveConn.dispose()


class ResponseCacheInterceptor(Interceptor):

    def __init__(self,mode:Literal['invalid-only','cache'],cacheType:Type[ResponseCacheInterface],hit_status_code=status.HTTP_200_OK):
        super().__init__()
        self.mode = mode
        self.cacheType = cacheType
        self.memCachedService = Get(MemCachedService)
        self.hit_status_code = hit_status_code

    async def intercept_before(self,request:Request,response:Response,template:str=None,):
        if self.mode == 'cache':

            result = await self.cacheType.Get(template,request=request)
            if result == None:
                return
            response.status_code = self.hit_status_code
            raise InterceptorDefaultException(response=copy_response(JSONResponse(result),response))

    async def intercept_after(self, result:Any,request:Request,response:Response,backgroundTasks:BackgroundTasks,template:str=None,):
        
        if self.mode == 'cache':
            backgroundTasks.add_task(self.cacheType.Set,template,result,request=request)
        else:
            backgroundTasks.add_task(self.cacheType.Delete,template,request=request)
        
        