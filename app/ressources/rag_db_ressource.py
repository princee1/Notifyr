from http import HTTPMethod
from app.definition._ressource import BaseHTTPRessource, HTTPRessource, IncludeRessource
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
    def get_description(self) -> str:
        return "RAG Databases management ressouce"