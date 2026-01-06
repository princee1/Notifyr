from fastapi import Request, Response
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, IncludeRessource,HTTPMethod
from app.ressources.rag.data_loader_ressource import DataLoaderRessource
from app.ressources.rag.kg_graph_ressource  import KGGraphDBRessource
from app.ressources.rag.vector_ressource  import VectorDBRessource


@IncludeRessource(DataLoaderRessource)
@IncludeRessource(KGGraphDBRessource)
@IncludeRessource(VectorDBRessource)
@HTTPRessource('rag-db')
class RagDBRessource(BaseHTTPRessource):
    
    def __init__(self):
        super().__init__(None,None)

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self,request:Request,response:Response):
        return "RAG Databases management ressource"