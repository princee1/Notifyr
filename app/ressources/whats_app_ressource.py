from definition._ressource import Ressource

WHATS_APP_PREFIX = '/whatsapp/'

class WhatsAppRessource(Ressource):
    def __init__(self,):
        super().__init__(WHATS_APP_PREFIX)
    
    ...