from typing import Annotated, Literal
from fastapi import Depends, Query, Request, Response
from app.container import InjectInMethod
from app.decorators.handlers import TortoiseHandler
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, UseHandler, UseLimiter
from app.depends.my_depends import get_link
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.link_service import LinkService
from fastapi.responses import RedirectResponse
from app.depends.variables import  verify_url
from app.models.link_model import LinkORM,LinkModel, UpdateLinkModel


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

    @HTTPStatusCode(201)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.POST])
    async def add_link(self, request: Request, linkModel: LinkModel, response: Response):
        link = linkModel.model_dump()
        link = await LinkORM.create(**link)
        return {"data": link.to_json, "message": "Link created successfully"}

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    def read_link(self, request: Request, link: Annotated[LinkORM, Depends(get_link)]):
        return {"data": link.to_json, "message": "Link retrieved successfully"}

    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.DELETE])
    async def delete_link(self, link: Annotated[LinkORM, Depends(get_link)], archive: bool = Query(False)):
        link_data = link.to_json.copy()
        await link.delete()
        return {"data": link_data, "message": "Link deleted successfully"}

    @HTTPStatusCode(200)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def update_link(self, link: Annotated[LinkORM, Depends(get_link)], linkUpdateModel: UpdateLinkModel,response:Response):
        link.expiration = linkUpdateModel.expiration
        link.link_name = linkUpdateModel.link_name
        await link.save()
        return {"data": link.to_json(), "message": "Link updated successfully"}

    
    @BaseHTTPRessource.HTTPRoute('/code/',methods=[HTTPMethod.GET])
    def get_qrcode(self,link:Annotated[LinkORM,Depends(get_link)],):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/verify',methods=[HTTPMethod.PATCH])
    def verify(self,request:Request,link:Annotated[LinkORM,Depends(get_link)],verify_type:Literal['well-known','domain']=Depends(verify_url)):
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


    
    

