from fastapi import Request, Response
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, IncludeRessource,HTTPMethod
from app.ressources.agentic.gateway.kg_graph_ressource  import KGGraphDBRessource
from app.ressources.agentic.gateway.vector_ressource  import VectorDBRessource


@IncludeRessource(KGGraphDBRessource)
@IncludeRessource(VectorDBRessource)
@HTTPRessource('rag-db')
class GatewayAgenticRessource(BaseHTTPRessource):
    
    def __init__(self):
        super().__init__(None,None)

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self,request:Request,response:Response):
        return "RAG Databases management ressource"