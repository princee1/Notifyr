from typing import Annotated
from fastapi import Depends, Request,status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.container import InjectInMethod
from app.definition._error import ServerFileError
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, MountDirectory, UseLimiter
from datetime import timedelta
from app.depends.funcs_dep import Get_Contact
from app.depends.orm_cache import ContactORMCache, ContactSummaryORMCache
from app.models.contacts_model import ContactORM, ContactSummary
from app.services.config_service import ConfigService
from app.services.contacts_service import ContactsService
from app.services.file_service import FileService
from app.services.link_service import LinkService
from app.utils.fileIO import FDFlag

APP_PREFIX=''
get_contacts = Get_Contact(True,True)

async def get_contacts_cache(contact_id:str):
    return await ContactORMCache.Cache(contact_id)

async def get_contacts_summary(contact_id:str)->ContactSummary:
    return await ContactSummaryORMCache.Cache(contact_id)

@MountDirectory(f'{APP_PREFIX}/me/',StaticFiles(directory='app/static/me/'),'me')
@HTTPRessource(APP_PREFIX,add_prefix=False)
class AppRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,fileService:FileService,contactService:ContactsService,linkService:LinkService,configService:ConfigService):
        super().__init__()
        self.fileService = fileService
        self.contactService = contactService
        self.linkService = linkService
        self.configService = configService

        self.templates = Jinja2Templates(directory='app/static/me/')

    def on_startup(self):
        super().on_startup()
        self.app_route_html_content = self.fileService.readFile('app/static/index.html',FDFlag.READ)
        self.landing_page_html_content = self.fileService.readFile('app/static/home/index.html',FDFlag.READ)
        self.me_page_html_content = self.fileService.readFile('app/static/me/index.html',FDFlag.READ)

    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.HTTPRoute('/',[HTTPMethod.GET],deprecated=True,mount=True,)
    def app_route(self,request:Request):
        cache_duration = int(timedelta(days=365).total_seconds())
        headers = {
            "Cache-Control": f"public, max-age={cache_duration}, immutable"
        }
        return HTMLResponse(self.app_route_html_content,headers=headers)
    
    @UseLimiter(limit_value='10000/day')
    @BaseHTTPRessource.HTTPRoute('/home/',[HTTPMethod.GET],deprecated=True,mount=True,)
    def landing_page(self,request:Request):
        cache_duration = int(timedelta(days=365).total_seconds())
        headers = {
            "Cache-Control": f"public, max-age={cache_duration}, immutable"
        }
        return HTMLResponse(self.landing_page_html_content,headers=headers)
        #return HTMLResponse()

    @BaseHTTPRessource.HTTPRoute('/me/{contact_id}/',[HTTPMethod.GET],deprecated=False,mount=True)
    async def me_page(self,request:Request,contact:Annotated[ContactSummary,Depends(get_contacts_summary)]):
        
        if contact == None:
            raise ServerFileError('app/static/error-404-page/index.html',status.HTTP_404_NOT_FOUND)

        return self.templates.TemplateResponse(request,'index.html',{
            **contact   
        })

    @BaseHTTPRessource.HTTPRoute('/.well-know/{system}.json',[HTTPMethod.GET],deprecated=True,mount=True,)
    def well_known(self,request:Request,system:str|None):

        return {
            'service':'notify'
        }