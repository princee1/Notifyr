from app.definition._ressource import BaseHTTPRessource, HTTPRessource

@HTTPRessource()
class MessageRessource(BaseHTTPRessource):
    
    def __init__(self):
        super().__init__(None,None)