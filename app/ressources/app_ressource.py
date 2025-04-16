from fastapi import Request
from fastapi.responses import FileResponse
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource

APP_PREFIX=''

@HTTPRessource(APP_PREFIX,add_prefix=False)
class AppRessource(BaseHTTPRessource):

    @BaseHTTPRessource.HTTPRoute('/',[HTTPMethod.GET],deprecated=True,mount=True,)
    def app_route(self,request:Request):
        return FileResponse('app/static/index.html')