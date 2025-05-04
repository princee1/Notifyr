from typing import Annotated, Literal
from urllib.parse import urlparse
from fastapi import BackgroundTasks, Depends, Query, Request, Response
from fastapi.staticfiles import StaticFiles
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
from fastapi import status
from fastapi.responses import FileResponse, RedirectResponse
from app.depends.variables import  verify_url
from app.models.link_model import LinkORM,LinkModel, QRCodeModel, UpdateLinkModel
from app.utils.helper import APIFilterInject

LINK_MANAGER_PREFIX = 'manage'

@APIFilterInject
def verify_link_guard(link:LinkORM):

    if link.public:
        return False,'Cannot verify public domain'
    if link.archived:
        return False, 'Cannot verify archived domain'
    if link.verified:
        return False, 'Already verified'

    return True

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

        public_security = {}
        link = await LinkORM.create(**link)

        if not link.public:
            signature, public_key = await self.linkService.generate_public_signature(link)
            public_security['signature'] = signature
            public_security['public_key'] = public_key

        return {"data": {**link.to_json}, "message": "Link created successfully"}

    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def read_link(self, request: Request, link: Annotated[LinkORM, Depends(get_link)],authPermission=Depends(get_auth_permission)):
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

    
    @UseRoles([Role.ADMIN])
    @UseGuard(verify_link_guard)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @BaseHTTPRessource.HTTPRoute('/verify',methods=[HTTPMethod.PATCH])
    async def verify(self,request:Request,link:Annotated[LinkORM,Depends(get_link)],response:Response,verify_type:Literal['well-known','domain']=Depends(verify_url)):
        
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
    
    @UseGuard(AccessLinkGuard(True))
    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/{link_id}/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    async def visit_url(self,request:Request,backgroundTask: BackgroundTasks,link:Annotated[LinkORM,Depends(get_link)],link_args:Annotated[LinkArgs,Depends(LinkArgs)]):
        path = None
        redirect_link = link_args.create_link(link,path,("session_id"))
                
        data = {**link_args.server_scoped}        
        parsed_info = self.linkService.parse_info(request,link.link_short_id,path)
        
        backgroundTask.add_task(self.redisService.publish_data,'links',data)
        backgroundTask.add_task(self.redisService.stream_data,'links',{**data,**parsed_info})

        return  RedirectResponse(redirect_link,status.HTTP_308_PERMANENT_REDIRECT)

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/email-track/{path}/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def track_email(self,request:Request,backgroundTask: BackgroundTasks,path:str,link_args:Annotated[LinkArgs,Depends(LinkArgs)]):

        message_id = link_args.server_scoped["message_id"]
        contact_id = link_args.server_scoped["contact_id"]

        data = {"message_id":message_id,"contact_id":contact_id}

        backgroundTask.add_task(self.redisService.publish_data,'emails',data)
        backgroundTask.add_task(self.redisService.stream_data,'emails',data)

        backgroundTask.add_task(self.redisService.publish_data,'links',{**link_args.server_scoped})

        if path:
            redirect_url = link_args.create_link(None,path,('contact_id'),('cid'))
            return RedirectResponse(redirect_url,status.HTTP_307_TEMPORARY_REDIRECT)

        return ''

    @UsePermission(JWTRouteHTTPPermission)
    @UseGuard(AccessLinkGuard)
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/code/{link_id}/', methods=[HTTPMethod.GET],mount=True)
    async def get_qrcode(self, link_id: str, qrModel: QRCodeModel, link: Annotated[LinkORM, Depends(get_link)], link_args: Annotated[LinkArgs, Depends(LinkArgs)],authPermission=Depends(get_auth_permission)):
        path: str = None
        url = link_args.create_link(link, path, ("contact_id", "message_id", "session_id"))
        img_data = await self.linkService.generate_qr_code(url, qrModel)
        return Response(content=img_data, media_type="image/png")
    
    

