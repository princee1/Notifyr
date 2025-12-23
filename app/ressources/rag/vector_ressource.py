from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource

@HTTPRessource('vector')
class VectorDBRessource(BaseHTTPRessource):
    ...

    def __init__(self):
        super().__init__(None,None)
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self) -> str:
        return "Vector Database management ressource"
    

    @BaseHTTPRessource.HTTPRoute('/collection',methods=[HTTPMethod.POST])
    async def create_collection(self,):
        ...