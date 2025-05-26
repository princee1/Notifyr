from typing import Annotated, Literal,get_args
from urllib.parse import urlparse
from fastapi import BackgroundTasks, Depends, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from app.classes.auth_permission import Role
from app.container import InjectInMethod
from app.decorators.guards import AccessLinkGuard
from app.decorators.handlers import ORMCacheHandler, TortoiseHandler
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._error import ServerFileError
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, HTTPStatusCode, UseGuard, UseHandler, UseLimiter, UsePermission, UsePipe, UseRoles
from app.depends.dependencies import get_auth_permission, get_query_params
from app.depends.funcs_dep import GetLink
from app.depends.class_dep import Broker, LinkQuery
from app.depends.orm_cache import LinkORMCache
from app.models.email_model import EmailStatus, TrackingEmailEventORM
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.database_service import RedisService
from app.services.link_service import LinkService
from fastapi import status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from app.depends.variables import  verify_url
from app.models.link_model import LinkORM,LinkModel, QRCodeModel, UpdateLinkModel
from app.utils.constant import  StreamConstant
from app.utils.helper import  uuid_v1_mc
from app.classes.broker import MessageBroker,MessageError
from tortoise.transactions import in_transaction
from datetime import datetime, timezone

LINK_MANAGER_PREFIX = 'manage'

get_link = GetLink(False)

MediaType=Literal['html_image,','html','image']

media_type_query = get_query_params(
    'media_type', 
    'html_image', 
    raise_except=True, 
    checker=lambda v: v in get_args(MediaType)
)

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
        domain = urlparse(link['link_url']).netloc
        async with in_transaction():
            if linkModel.public:
                self.linkService.verify_safe_domain(domain)

            public_security = {}
            link = await LinkORM.create(**link)

            if not link.public:
                public_key = await self.linkService.generate_public_signature(link)
                public_security['public_key'] = public_key
            else:
                await LinkORMCache.Store(link.link_short_id,link)
            return {"data": {**link.to_json},"security":public_security,  "message": "Link created successfully"}

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
    @UseGuard(AccessLinkGuard.verify_link_guard)
    @HTTPStatusCode(status.HTTP_200_OK)
    @BaseHTTPRessource.HTTPRoute('/verify', methods=[HTTPMethod.PATCH])
    async def verify(self, request: Request, link: Annotated[LinkORM, Depends(get_link)], response: Response, verify_type: Literal['well-known', 'domain'] = Depends(verify_url)):
        
        public_key = await self.linkService.get_server_well_know(link)
        ownership = await self.linkService.verify_public_signature(link, public_key)
        if ownership:
            link.verified = True
            link.expiration_verification = None
            await link.save()
            await LinkORMCache.Store(link.link_short_id, link)
            return {"data": link.to_json(), "message": "Link verified successfully"}

        return {"error": "Verification failed", "message": "Unable to verify the link ownership"}

    @UseGuard(AccessLinkGuard(False))
    @UseRoles([Role.PUBLIC])
    @HTTPStatusCode(200)
    @BaseHTTPRessource.HTTPRoute('/code/{link_id}/', methods=[HTTPMethod.GET,HTTPMethod.POST], mount=True)
    async def get_qrcode(self,response:Response, link_id: str, qrModel: QRCodeModel, link: Annotated[LinkORM, Depends(get_link)], link_query: Annotated[LinkQuery, Depends(LinkQuery)], media_type: MediaType = Depends(media_type_query), authPermission=Depends(get_auth_permission)):
        path: str = None
        url = link_query.create_link(link, path, ("contact_id", "message_id", "session_id"))
        img_data = await self.linkService.generate_qr_code(url, qrModel)

        if media_type == "image":
            headers = {
                "Content-Disposition": f"attachment; filename={link_id}.png"
            }
            return Response(content=img_data, media_type="image/png", headers=headers)
        elif media_type == "html":
            html_content = self.linkService.generate_html(img_data)
            return HTMLResponse(content=html_content, media_type="text/html")
        else:
            return PlainTextResponse(content=img_data,media_type="image/png")

LINK_PREFIX='link'
@HTTPRessource(LINK_PREFIX,routers=[CRUDLinkRessource])
class LinkRessource(BaseHTTPRessource):
    
    @InjectInMethod
    def __init__(self,configService:ConfigService,redisService:RedisService,linkService:LinkService,contactService:ContactsService):
        super().__init__()
        self.configService = configService
        self.redisService = redisService
        self.linkService = linkService
        self.contactService = contactService
    
    @UseGuard(AccessLinkGuard(True))
    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/v/{link_id}/{path:path}',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    async def track_visit_url(self,request:Request,response:Response,path:str,broker:Annotated[Broker,Depends(Broker)],link:Annotated[LinkORM,Depends(get_link_cache)],link_query:Annotated[LinkQuery,Depends(LinkQuery)]):

        redirect_link = link_query.create_link(link,path,("session_id"))
        sid_type,subject_id = link_query.subject_id

        saved_info = await self.linkService.parse_info(request,link.link_id,path,link_query)
       
        broker.publish(StreamConstant.LINKS_EVENT_STREAM,sid_type,subject_id,saved_info,)
        broker.stream(StreamConstant.LINKS_EVENT_STREAM,saved_info)
        
        return  RedirectResponse(redirect_link,status.HTTP_308_PERMANENT_REDIRECT,)

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/t/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def track_email_links(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],link_query:Annotated[LinkQuery,Depends(LinkQuery)]):
        self.send_email_event(broker, link_query,EmailStatus.LINK_CLICKED.value)
        
        redirect_url = link_query.redirect_url
        redirect_url = link_query.create_link(redirect_url,None,('contact_id','message_id'),('cid'))
        return RedirectResponse(redirect_url,status.HTTP_308_PERMANENT_REDIRECT)

    @UseLimiter(limit_value='10000/min')
    @BaseHTTPRessource.HTTPRoute('/p/',methods=[HTTPMethod.GET,HTTPMethod.POST],mount=True)
    def track_pixel(self,request:Request,response:Response,broker:Annotated[Broker,Depends(Broker)],link_query:Annotated[LinkQuery,Depends(LinkQuery)]):
        self.send_email_event(broker,link_query,EmailStatus.OPENED.value)
        return None
    

    def send_email_event(self, broker:Broker, link_query:LinkQuery,event:EmailStatus):
        message_id = link_query['message_id']
        contact_id = link_query['contact_id']
        now = datetime.now(timezone.utc).isoformat()

        if contact_id: 
            # TODO track contact event
            broker.publish(StreamConstant.CONTACT_EVENT,'contact',contact_id,{},)

        data = TrackingEmailEventORM.TrackingEventJSON(event_id=uuid_v1_mc(),email_id=message_id,contact_id=contact_id,current_event=event,date_event_received=now)

        broker.publish(StreamConstant.EMAIL_EVENT_STREAM,'message',message_id,data,)
        broker.stream(StreamConstant.EMAIL_EVENT_STREAM,data)
