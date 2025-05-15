from typing import Annotated, Literal
from urllib.parse import urlparse
from fastapi import BackgroundTasks, Depends, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.guards import AccessLinkGuard
from app.decorators.handlers import ORMCacheHandler, TortoiseHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, UseGuard, UseHandler, UseLimiter, UsePermission, UseRoles
from app.depends.dependencies import get_auth_permission
from app.depends.funcs_dep import GetLink
from app.depends.class_dep import Broker, LinkArgs
from app.depends.orm_cache import LinkORMCache
from app.models.email_model import EmailStatus, TrackingEmailEventORM
from app.services.config_service import ConfigService
from app.services.database_service import RedisService
from app.services.link_service import LinkService
from fastapi import status
from fastapi.responses import FileResponse, RedirectResponse
from app.depends.variables import  verify_url
from app.models.link_model import LinkORM,LinkModel, QRCodeModel, UpdateLinkModel
from app.utils.constant import StreamConstant
from app.utils.helper import APIFilterInject, uuid_v1_mc
from app.classes.broker import MessageBroker,MessageError

LINK_MANAGER_PREFIX = 'manage'

get_link = GetLink(False)

@APIFilterInject
def verify_link_guard(link:LinkORM):

    if link.public:
        return False,'Cannot verify public domain'
    if link.archived:
        return False, 'Cannot verify archived domain'
    if link.verified:
        return False, 'Already verified'

    return True

async def get_link_cache(link_id:str,)->LinkORM:
    return await LinkORMCache.Cache(link_id,link_id,lid="sid")


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
    @UseHandler(ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.POST])
    async def add_link(self, request: Request, linkModel: LinkModel, response: Response,authPermission=Depends(get_auth_permission)):
        link = linkModel.model_dump()
        domain = urlparse(link['link_url']).hostname

        if linkModel.public:
            self.linkService.verify_safe_domain(domain)

        public_security = {}
        link = await LinkORM.create(**link)

        if not link.public:
            signature, public_key = await self.linkService.generate_public_signature(link)
            public_security['signature'] = signature
            public_security['public_key'] = public_key
        else:
            await LinkORMCache.Store(link.link_short_id,link)
        return {"data": {**link.to_json}, "message": "Link created successfully"}

    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.GET])
    async def read_link(self, request: Request, link: Annotated[LinkORM, Depends(get_link)],authPermission=Depends(get_auth_permission)):
        return {"data": link.to_json, "message": "Link retrieved successfully"}

    @UseRoles([Role.ADMIN])
    @UseHandler(ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.DELETE])
    async def delete_link(self, link: Annotated[LinkORM, Depends(get_link)], archive: bool = Query(False),authPermission=Depends(get_auth_permission)):
        link_data = link.to_json.copy()
        if not archive:
            await link.delete()
            await LinkORMCache.Invalid(link.link_short_id)
            return {"data": link_data, "message": "Link deleted successfully"}
        
        link.archived = True
        await link.save()
        await LinkORMCache.Invalid(link.link_short_id)
        return {"data": link_data, "message": "Link archived successfully"}

    @UseRoles([Role.ADMIN])
    @HTTPStatusCode(200)
    @UseHandler(ORMCacheHandler)
    @BaseHTTPRessource.HTTPRoute('/', methods=[HTTPMethod.PUT])
    async def update_link(self, link: Annotated[LinkORM, Depends(get_link)], linkUpdateModel: UpdateLinkModel,response:Response,authPermission=Depends(get_auth_permission)):
        if linkUpdateModel.archived != None:
            link.archived = linkUpdateModel.archived
        
        if linkUpdateModel.expiration:
            link.expiration = linkUpdateModel.expiration
        
        if linkUpdateModel.link_name:
            link.link_name = linkUpdateModel.link_name

        await link.save()
        await LinkORMCache.Invalid(link.link_short_id)
        return {"data": link.to_json(), "message": "Link updated successfully"}

    
    @UseRoles([Role.ADMIN])
    @UseGuard(verify_link_guard)
    @HTTPStatusCode(status.HTTP_204_NO_CONTENT)
    @BaseHTTPRessource.HTTPRoute('/verify',methods=[HTTPMethod.PATCH])
    async def verify(self,request:Request,link:Annotated[LinkORM,Depends(get_link)],response:Response,verify_type:Literal['well-known','domain']=Depends(verify_url)):
        
        domain = urlparse(link.link_url).hostname
        await self.linkService.get_server_well_know(link)
        await self.linkService.verify_public_signature(link)
        await LinkORMCache.Store(link.link_short_id,link)

        

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
    @BaseHTTPRessource.HTTPRoute('/v/{link_id}/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    async def visit_url(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],link:Annotated[LinkORM,Depends(get_link_cache)],link_args:Annotated[LinkArgs,Depends(LinkArgs)]):
        path = None
        redirect_link = link_args.create_link(link,path,("session_id"))
        sid_type,subject_id = link_args.subject_id

        saved_info = await self.linkService.parse_info(request,link.link_id,path,link_args)
        message_id = link_args.server_scoped.get('message_id',None)
        contact_id = link_args.server_scoped.get('contact_id',None)

        broker.publish(StreamConstant.LINKS_EVENT_STREAM,sid_type,subject_id,saved_info,)
        broker.stream(StreamConstant.LINKS_EVENT_STREAM,saved_info)
        
        if message_id:
            email_event= TrackingEmailEventORM.TrackingEventJSON(contact_id=contact_id,email_id=message_id,event_id=uuid_v1_mc(),current_event=EmailStatus.LINK_CLICKED.value)
            broker.publish(StreamConstant.EMAIL_EVENT_STREAM,'message',message_id,email_event)
            broker.stream(StreamConstant.EMAIL_EVENT_STREAM,email_event,)
        
        return  RedirectResponse(redirect_link,status.HTTP_308_PERMANENT_REDIRECT,)

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/t/{path}/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=False)
    def track_email(self,request:Request,response:Response,path:str,broker:Annotated[Broker,Depends(Broker)],link_args:Annotated[LinkArgs,Depends(LinkArgs)]):

        sid_type,subject_id = link_args.subject_id
        data = {}
        broker.publish(StreamConstant.EMAIL_EVENT_STREAM,'message',subject_id,data,)
        broker.stream(StreamConstant.EMAIL_EVENT_STREAM,data)

        if path:
            redirect_url = link_args.create_link(None,path,('contact_id'),('cid'))
            return RedirectResponse(redirect_url,status.HTTP_308_PERMANENT_REDIRECT)

        return None

    @UsePermission(JWTRouteHTTPPermission)
    @UseGuard(AccessLinkGuard)
    @UseRoles([Role.PUBLIC])
    @BaseHTTPRessource.HTTPRoute('/code/{link_id}/', methods=[HTTPMethod.GET],mount=True)
    async def get_qrcode(self, link_id: str, qrModel: QRCodeModel, link: Annotated[LinkORM, Depends(get_link)], link_args: Annotated[LinkArgs, Depends(LinkArgs)],authPermission=Depends(get_auth_permission)):
        path: str = None
        url = link_args.create_link(link, path, ("contact_id", "message_id", "session_id"))
        img_data = await self.linkService.generate_qr_code(url, qrModel)
        return Response(content=img_data, media_type="image/png")
    
    
    async def ip_lookup(self,ip_address):
        ...
