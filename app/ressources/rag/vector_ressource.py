from app.definition._ressource import BaseHTTPRessource, HTTPMethod, HTTPRessource

@HTTPRessource('vector')
class VectorDBRessource(BaseHTTPRessource):
    ...

    def __init__(self):
        super().__init__(None,None)
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    def get_description(self) -> str:
        return "Vector Database management ressource"
    

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.POST])
    async def create_collection(self,):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.GET])
    async def get_collection(self):
        ...
    
    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.DELETE])
    async def delete_collection(self):
        ...

    @BaseHTTPRessource.HTTPRoute('/',methods=[HTTPMethod.PUT])
    async def update_collection(self):
        ...
    
    async def get_all_collection(self):
        ...