from app.definition._ressource import BaseHTTPRessource, HTTPRessource, IncludeRessource
from app.ressources.rag.kg_graph_ressource  import KGGraphDBRessource
from app.ressources.rag.vector_ressource  import VectorDBRessource


@IncludeRessource(KGGraphDBRessource)
@IncludeRessource(VectorDBRessource)
@HTTPRessource('rag-db')
class RagDBRessource(BaseHTTPRessource):
    
    def __init__(self):
        super().__init__(None,None)

    