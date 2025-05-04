from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UseLimiter
from datetime import timedelta

APP_PREFIX=''

@HTTPRessource(APP_PREFIX,add_prefix=False)
class AppRessource(BaseHTTPRessource):



    @UseLimiter(limit_value='10/day')
    @BaseHTTPRessource.HTTPRoute('/',[HTTPMethod.GET],deprecated=True,mount=True,)
    def app_route(self,request:Request):
        cache_duration = int(timedelta(days=365).total_seconds())
        headers = {
            "Cache-Control": f"public, max-age={cache_duration}, immutable"
        }
        return StaticFiles('app/static/index.html',html=True)

    @UseLimiter(limit_value='10000/day')
    @BaseHTTPRessource.HTTPRoute('/example-landing-page',[HTTPMethod.GET],deprecated=True,mount=True,)
    def landing_page(self,request:Request):
        cache_duration = int(timedelta(days=365).total_seconds())
        headers = {
            "Cache-Control": f"public, max-age={cache_duration}, immutable"
        }
        return StaticFiles('app/static/landing-page/index.html',html=True)
        #return HTMLResponse()