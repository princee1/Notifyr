from http import HTTPMethod

from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource
from app.depends.dependencies import get_auth_permission

@HTTPRessource('graph')
class KGGraphDBRessource(BaseHTTPRessource):

    def __init__(self):
        super().__init__(None,None)
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self) -> str:
        return "Knowledge Graph Database management ressource"

    
    
    