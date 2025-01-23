from app.definition._ressource import BaseHTTPRessource, HTTPRessource

WHATS_APP_PREFIX = '/whatsapp'

@HTTPRessource(WHATS_APP_PREFIX)
class WhatsAppRessource(BaseHTTPRessource):
    def __init__(self,):
        super().__init__()
    
    ...