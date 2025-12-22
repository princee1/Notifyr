from typing import Annotated
from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission, Role
from app.container import InjectInMethod
from app.decorators.handlers import AsyncIOHandler, MemCachedHandler, ServiceAvailabilityHandler, TortoiseHandler
from app.decorators.interceptors import DataCostInterceptor, ResponseCacheInterceptor
from app.decorators.permissions import AdminPermission, JWTRouteHTTPPermission, JWTStaticObjectPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, IncludeRessource, UseHandler, UseInterceptor, UseLimiter, UsePermission, UseRoles
from app.depends.dependencies import get_auth_permission
from app.services.object_service import ObjectS3Service
from app.services.config_service import ConfigService
from app.services.security_service import SecurityService,JWTAuthService
from app.definition._cost import DataCost


@HTTPRessource('social')
class SocialBlogRessource(BaseHTTPRessource):
    ...

    @UseLimiter('1/sec')
    @UseInterceptor(ResponseCacheInterceptor('invalid-only'))
    @BaseHTTPRessource.HTTPRoute('/like/{blog}/',methods=[HTTPMethod.POST])
    async def like_blog(self,blog:str,request:Request,response:Response):
        ...
    
    @UseLimiter('1/sec')
    @UseInterceptor(ResponseCacheInterceptor('invalid-only'))
    @BaseHTTPRessource.HTTPRoute('/comment/{comment}/{blog}/',methods=[HTTPMethod.POST])
    async def comment_blog(self,blog:str,comment:str,request:Request,response:Response):
        ...
    
    @UseLimiter('1/sec')
    @UseHandler(MemCachedHandler)
    @UseInterceptor(ResponseCacheInterceptor('cache'))
    @BaseHTTPRessource.HTTPRoute('/{blog}/',methods=[HTTPMethod.GET])
    async def get_blog(self,blog:str,request:Request,response:Response):
        ...


@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler,AsyncIOHandler,TortoiseHandler,MemCachedHandler)
@IncludeRessource(SocialBlogRessource)
@HTTPRessource('blogs')
class BlogsRessource(BaseHTTPRessource):

    @InjectInMethod()
    def __init__(self,configService:ConfigService,awsS3Service:ObjectS3Service):
        super().__init__()
        self.configService = configService
        self.awsS3Service = awsS3Service

    @UsePermission(AdminPermission)
    @UseInterceptor(DataCostInterceptor)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_blog(self,request:Request, response:Response,cost:Annotated[DataCost,Depends(DataCost)],authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.STATIC])
    @UsePermission(JWTStaticObjectPermission)
    @UseInterceptor(ResponseCacheInterceptor('invalid-only'))
    @BaseHTTPRessource.HTTPRoute('/{blog}/',methods=[HTTPMethod.GET])
    async def modify_blog(self,blog:str,request:Request,response:Response,authPermission:AuthPermission=Depends(get_auth_permission)):
        ...

    @UseRoles([Role.PUBLIC])
    @UseInterceptor(ResponseCacheInterceptor('cache'))
    @BaseHTTPRessource.HTTPRoute('/{blog}/',methods=[HTTPMethod.GET])
    async def get_blog(self,blog:str,request:Request,response:Response):
        ...

    @UsePermission(AdminPermission)
    @UseInterceptor(DataCostInterceptor)
    @UseInterceptor(ResponseCacheInterceptor('invalid-only'))
    @BaseHTTPRessource.HTTPRoute('/{blog}/',methods=[HTTPMethod.DELETE])
    async def delete_blog(self,blog:str,request:Request,response:Response,cost:Annotated[DataCost,Depends(DataCost)],authPermission:AuthPermission=Depends(get_auth_permission)): # type: ignore
        ...