from http import HTTPMethod
from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource

@HTTPRessource('kg')
class KGGraphDBRessource(BaseHTTPRessource):

    def __init__(self):
        super().__init__(None,None)
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self) -> str:
        return "Knowledge Graph Database management ressource"