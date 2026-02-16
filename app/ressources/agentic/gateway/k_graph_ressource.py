from fastapi import Depends, Request, Response
from app.classes.auth_permission import AuthPermission
from app.decorators.permissions import JWTRouteHTTPPermission
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource, UsePermission
from app.depends.dependencies import get_auth_permission

@UsePermission(JWTRouteHTTPPermission)
@HTTPRessource('k-graph')
class KGraphDBRessource(BaseHTTPRessource):

    def __init__(self):
        super().__init__(None,None)
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self,response:Response,request:Request,authPermission:AuthPermission= Depends(get_auth_permission)):
        return "Knowledge Graph Database management ressource"

    
    async def get_node(self,uuid:str):
        ...

    async def delete_node(self,uuid:str):
        ...

    async def get_document_graph(self,document_id:str):
        ...

    async def delete_document(self,document_id:str):
        ...

    async def get_domain_graph(self,domain:str):
        ...
    
    async def delete_domain(self,domain:str):
        ...