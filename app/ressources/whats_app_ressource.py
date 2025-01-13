from definition._ressource import BaseRessource, Ressource

WHATS_APP_PREFIX = '/whatsapp'

@Ressource(WHATS_APP_PREFIX)
class WhatsAppRessource(BaseRessource):
    def __init__(self,):
        super().__init__()
    
    ...