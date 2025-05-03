from typing import Annotated, Literal
from urllib.parse import urlparse
from fastapi import Depends, Query, Request, Response
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.guards import AccessLinkGuard
from app.decorators.handlers import TortoiseHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, UseGuard, UseHandler, UseLimiter, UsePermission, UseRoles
from app.depends.dependencies import get_auth_permission
from app.depends.my_depends import LinkArgs, get_link
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.link_service import LinkService
from fastapi.responses import FileResponse, RedirectResponse
from app.depends.variables import  verify_url
from app.models.link_model import LinkORM,LinkModel, QRCodeModel, UpdateLinkModel


LINK_MANAGER_PREFIX = 'manage'

@UseRoles([Role.LINK])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(TortoiseHandler)
@HTTPRessource(LINK_MANAGER_PREFIX)
class CRUDLinkRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,linkService:LinkService):
        super().__init__()
        self.configService = configService
        self.linkService = linkService

    @UseRoles([Role.ADMIN])
    @HTTPStatusCode(201)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.POST])
    async def add_link(self, request: Request, linkModel: LinkModel, response: Response,authPermission=Depends(get_auth_permission)):
        link = linkModel.model_dump()
        domain = urlparse(link['link_url']).hostname

        if not linkModel.public:
            self.linkService.verify_safe_domain(domain)

        link = await LinkORM.create(**link)
        signature, public_key = await self.linkService.generate_public_signature(link)
        return {"data": link.to_json, "message": "Link created successfully"}

    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    def read_link(self, request: Request, link: Annotated[LinkORM, Depends(get_link)],authPermission=Depends(get_auth_permission)):
        return {"data": link.to_json, "message": "Link retrieved successfully"}

    @UseRoles([Role.ADMIN])
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.DELETE])
    async def delete_link(self, link: Annotated[LinkORM, Depends(get_link)], archive: bool = Query(False),authPermission=Depends(get_auth_permission)):
        link_data = link.to_json.copy()
        if not archive:
            await link.delete()
            return {"data": link_data, "message": "Link deleted successfully"}
        
        link.archived = True
        await link.save()
        return {"data": link_data, "message": "Link archived successfully"}

    @UseRoles([Role.ADMIN])
    @HTTPStatusCode(200)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def update_link(self, link: Annotated[LinkORM, Depends(get_link)], linkUpdateModel: UpdateLinkModel,response:Response,authPermission=Depends(get_auth_permission)):
        if linkUpdateModel.archived != None:
            link.archived = linkUpdateModel.archived
        
        if linkUpdateModel.expiration:
            link.expiration = linkUpdateModel.expiration
        
        if linkUpdateModel.link_name:
            link.link_name = linkUpdateModel.link_name

        await link.save()
        return {"data": link.to_json(), "message": "Link updated successfully"}

    @UseGuard(AccessLinkGuard)
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/code/{link_id}/{path}', methods=[HTTPMethod.GET])
    async def get_qrcode(self, link_id: str, path: str, qrModel: QRCodeModel, link: Annotated[LinkORM, Depends(get_link)], link_args: Annotated[LinkArgs, Depends(LinkArgs)]):
        url = link_args.create_link(link, path, ("contact_id", "message_id", "session_id"))
        img_data = await self.linkService.generate_qr_code(url, qrModel)
        return Response(content=img_data, media_type="image/png")
        
    
    @UseRoles([Role.ADMIN])
    @BaseHTTPRessource.HTTPRoute('/verify',methods=[HTTPMethod.PATCH])
    async def verify(self,request:Request,link:Annotated[LinkORM,Depends(get_link)],verify_type:Literal['well-known','domain']=Depends(verify_url)):
        domain = urlparse(link.link_url).hostname
        await self.linkService.get_server_well_know(link)
        await self.linkService.verify_public_signature(link)
        


    
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
    @BaseHTTPRessource.HTTPRoute('visits/{link_id}/{path}',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def visit_url(self,request:Request,path:str,link:Annotated[LinkORM,Depends(get_link)],link_args:Annotated[LinkArgs,Depends(LinkArgs)]):
        flag,_=AccessLinkGuard().do(**{'link':link})
        redirect_link = link_args.create_link(link,path)

        if not flag:
            return FileResponse('app/static/error-404-page/index.html')
        ... 

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/email-track/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def track_email(self,request:Request,link_args:Annotated[LinkArgs,Depends(LinkArgs)]):
        ...


    
    

