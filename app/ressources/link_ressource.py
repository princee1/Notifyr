from typing import Literal
from fastapi import Depends, Query, Request
from app.container import InjectInMethod
from app.decorators.handlers import TortoiseHandler
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseHandler, UseLimiter
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.link_service import LinkService
from fastapi.responses import RedirectResponse
from app.depends.variables import  verify_url

LINK_MANAGER_PREFIX = 'manage'
 
@UseHandler(TortoiseHandler)
@HTTPRessource(LINK_MANAGER_PREFIX)
class CRUDLinkRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,redisService:RedisService,linkService:LinkService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.linkService = linkService

    @UseHandler(TortoiseHandler)
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    def add_link(self,):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def read_link(self,request:Request,all:bool=Query(False)):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE])
    def delete_link(self,archive:bool=Query(False)):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT])
    def update_link(self,):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/code/',methods=[HTTPMethod.GET])
    def get_qrcode(self,):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/verify',methods=[HTTPMethod.PATCH])
    def verify(self,request:Request,verify_type:Literal['well-known','domain']=Depends(verify_url)):
        ...

    
LINK_PREFIX='link'
@HTTPRessource(LINK_PREFIX,routers=[CRUDLinkRessource])
class LinkRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,configService:ConfigService,redisService:RedisService,linkService:LinkService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.linkService = linkService
    

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/visits/{url}',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def visit_url(self,request:Request,url:str):
        
        ... 

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/email-track/{url}',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def track_email(self,request:Request,url):
        ...


    
    

