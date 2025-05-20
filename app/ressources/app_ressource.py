from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.container import InjectInMethod
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseLimiter
from datetime import timedelta

from app.services.file_service import FileService
from app.utils.fileIO import FDFlag

APP_PREFIX=''

@HTTPRessource(APP_PREFIX,add_prefix=False)
class AppRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,fileService:FileService):
        super().__init__()
        self.fileService = fileService

    def on_startup(self):
        super().on_startup()
        self.app_route_html_content = self.fileService.readFile('app/static/index.html',FDFlag.READ)
        self.landing_page_html_content = self.fileService.readFile('app/static/landing-page/index.html',FDFlag.READ)

    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.HTTPRoute('/',[HTTPMethod.GET],deprecated=True,mount=True,)
    def app_route(self,request:Request):
        cache_duration = int(timedelta(days=365).total_seconds())
        headers = {
            "Cache-Control": f"public, max-age={cache_duration}, immutable"
        }
        return HTMLResponse(self.app_route_html_content,headers=headers)

    @UseLimiter(limit_value='10000/day')
    @BaseHTTPRessource.HTTPRoute('/landing-page',[HTTPMethod.GET],deprecated=True,mount=True,)
    def landing_page(self,request:Request):
        cache_duration = int(timedelta(days=365).total_seconds())
        headers = {
            "Cache-Control": f"public, max-age={cache_duration}, immutable"
        }
        return HTMLResponse(self.landing_page_html_content,headers=headers)
        #return HTMLResponse()

    @BaseHTTPRessource.HTTPRoute('/.well-know/{system}',[HTTPMethod.GET],deprecated=True,mount=True,)
    def well_known(self,request:Request,system:str|None):

        return {
            'service':'notify'
        }