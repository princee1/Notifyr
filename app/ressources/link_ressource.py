from fastapi import Request
from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseLimiter
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.link_service import LinkService
from fastapi.responses import RedirectResponse

LINK_MANAGER_PREFIX = 'manage'
 
@HTTPRessource(LINK_MANAGER_PREFIX)
class CRUDLinkRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,redisService:RedisService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService

    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    def create_link(self,):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def read_link(self,):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE])
    def delete_link(self,):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT])
    def update_link(self,):
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
    @BaseHTTPRessource.HTTPRoute('/{url}',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def visit_url(self,request:Request,url:str):
        
        ... 

    @BaseHTTPRessource.HTTPRoute('/email-track/{url}',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def track_email(self,request:Request,url):
        ...

    

    
    

